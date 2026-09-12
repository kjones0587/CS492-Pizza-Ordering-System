import random
import string
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
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
        status='Received',
        created_at=datetime.now(timezone.utc)
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

    # Clear customer session cart
    session['cart'] = []
    session.modified = True

    return redirect(url_for('order.confirmation', order_number=order_num))

@order_bp.route('/confirmation/<order_number>')
def confirmation(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    item_count = sum(item.quantity for item in order.items)
    estimates = get_fulfillment_estimates(item_count)
    return render_template('confirmation.html', order=order, estimates=estimates, item_count=item_count)
