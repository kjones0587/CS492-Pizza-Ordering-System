import random
import string
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from app.models import db, Order, OrderItem
from app.routes.cart import get_cart, calculate_totals, get_fulfillment_estimates

order_bp = Blueprint('order', __name__)

def generate_order_number():
    date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ORD-{date_str}-{suffix}"

@order_bp.route('/submit', methods=['POST'])
def submit_order():
    cart = get_cart()
    if not cart:
        flash('Cannot submit an empty order. Please add items to your cart.', 'danger')
        return redirect(url_for('menu.index'))

    # Extract and validate form fields
    customer_name = request.form.get('customer_name', '').strip()
    customer_email = request.form.get('customer_email', '').strip()
    customer_phone = request.form.get('customer_phone', '').strip()
    order_type = request.form.get('order_type', 'pickup').strip().lower()
    delivery_address = request.form.get('delivery_address', '').strip()
    special_instructions = request.form.get('special_instructions', '').strip()
    payment_method = request.form.get('payment_method', 'cash').strip().lower()
    cardholder_name = request.form.get('name_on_card', '').strip()
    billing_zip = request.form.get('billing_zip', '').strip()

    # Preserve customer inputs in session so data is retained on any failure or decline
    session['checkout_form_data'] = {
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'order_type': order_type,
        'delivery_address': delivery_address,
        'special_instructions': special_instructions,
        'payment_method': payment_method,
        'name_on_card': cardholder_name,
        'billing_zip': billing_zip
    }
    session['order_type'] = order_type
    session.modified = True

    errors = []
    if not customer_name:
        errors.append('Customer Name is required.')
    if not customer_email or '@' not in customer_email:
        errors.append('A valid Email address is required.')
    if not customer_phone:
        errors.append('Phone Number is required.')
    if order_type not in ['pickup', 'delivery']:
        errors.append('Please select either Pickup or Delivery.')
    if order_type == 'delivery' and not delivery_address:
        errors.append('Delivery Address is required for delivery orders.')

    if errors:
        for err in errors:
            flash(err, 'danger')
        return redirect(url_for('cart.checkout'))

    # Calculate final certified bill totals
    totals = calculate_totals(cart, order_type=order_type)
    total_amount = totals['total_amount']

    # Task T2-06 (PB-06: Online Payment Processing - Kellen Jones)
    card_brand = None
    card_last4 = None
    transaction_id = None
    payment_status = 'Paid'

    if total_amount <= 0.0:
        # Full bill waived via promotional VIP pass (e.g. ALMASRI)
        payment_method = 'vip_pass'
        payment_status = 'Paid (Faculty Pass)'
        transaction_id = f"TXN-VIP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-0000"
    elif payment_method == 'cash':
        payment_status = 'Pending (Due on Pickup/Delivery)'
    elif payment_method == 'credit_card':
        from app.services.payment import process_mock_payment
        card_number = request.form.get('card_number', '').strip()
        exp_date = request.form.get('exp_date', '').strip()
        cvv = request.form.get('cvv', '').strip()

        pay_res = process_mock_payment(
            amount=total_amount,
            card_number=card_number,
            exp_date=exp_date,
            cvv=cvv,
            cardholder_name=cardholder_name,
            billing_zip=billing_zip
        )

        if not pay_res['success']:
            if 'checkout_form_data' in session:
                session['checkout_form_data']['payment_error'] = pay_res['error']
                session.modified = True
            flash(f"Payment Processing Error: {pay_res['error']}", 'danger')
            return redirect(url_for('cart.checkout'))

        card_brand = pay_res['card_brand']
        card_last4 = pay_res['card_last4']
        transaction_id = pay_res['transaction_id']
        payment_status = 'Paid'
    else:
        payment_method = 'cash'
        payment_status = 'Pending (Due on Pickup/Delivery)'

    order_num = generate_order_number()
    new_order = Order(
        order_number=order_num,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        order_type=order_type,
        delivery_address=delivery_address if order_type == 'delivery' else None,
        special_instructions=special_instructions or None,
        subtotal=totals['subtotal'],
        tax_amount=totals['tax_amount'],
        delivery_fee=totals['delivery_fee'],
        total_amount=totals['total_amount'],
        discount_amount=totals['discount_amount'],
        promo_code=totals['promo_code'],
        status='Received',
        created_at=datetime.now(timezone.utc),
        payment_method=payment_method,
        payment_status=payment_status,
        card_brand=card_brand,
        card_last4=card_last4,
        transaction_id=transaction_id
    )

    db.session.add(new_order)
    db.session.flush()

    for item in cart:
        toppings_val = ", ".join(item.get('toppings', [])) if item.get('toppings') else None
        order_item = OrderItem(
            order_id=new_order.id,
            menu_item_id=item.get('menu_item_id'),
            item_name=item.get('name'),
            size_option=item.get('size_option'),
            crust_option=item.get('crust_option'),
            toppings=toppings_val,
            special_notes=item.get('special_notes'),
            unit_price=item.get('unit_price'),
            quantity=item.get('quantity', 1),
            line_total=item.get('line_total')
        )
        db.session.add(order_item)

    db.session.commit()

    # Clear customer session cart, active promo, and preserved checkout form data
    session['cart'] = []
    session.pop('promo_code', None)
    session.pop('checkout_form_data', None)
    session.modified = True

    return redirect(url_for('order.confirmation', order_number=order_num))

@order_bp.route('/confirmation/<order_number>')
def confirmation(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    item_count = sum(item.quantity for item in order.items)
    estimates = get_fulfillment_estimates(item_count)
    return render_template('confirmation.html', order=order, estimates=estimates, item_count=item_count)

@order_bp.route('/<order_number>/track')
def track_order(order_number):
    """Live visual order progress tracker (PB-05 / PB-10: Ayden Lotter)"""
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    item_count = sum(item.quantity for item in order.items)
    estimates = get_fulfillment_estimates(item_count)

    # Step numbers: 1=Received, 2=Preparing, 3=Stone Oven Baking, 4=Ready for Pickup/Delivery, 5=Completed
    status_map = {
        'Received': 1,
        'Preparing': 2,
        'Ready': 4,
        'Completed': 5,
        'Cancelled': -1
    }
    current_step = status_map.get(order.status, 1)

    return render_template(
        'track.html',
        order=order,
        estimates=estimates,
        item_count=item_count,
        current_step=current_step
    )

@order_bp.route('/api/<order_number>/status')
def order_status_api(order_number):
    """API endpoint for live order tracking polling (PB-05 / PB-10: Ayden Lotter)"""
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    status_map = {
        'Received': 1,
        'Preparing': 2,
        'Ready': 4,
        'Completed': 5,
        'Cancelled': -1
    }
    return jsonify({
        'success': True,
        'order_number': order.order_number,
        'status': order.status,
        'current_step': status_map.get(order.status, 1),
        'order_type': order.order_type,
        'customer_name': order.customer_name
    })

