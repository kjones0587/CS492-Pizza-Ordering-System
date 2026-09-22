import random
import string
import re
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
    session['active_order_number'] = order_num
    session.modified = True

    return redirect(url_for('order.confirmation', order_number=order_num))

@order_bp.route('/confirmation/<order_number>')
def confirmation(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    session['active_order_number'] = order.order_number
    session.modified = True
    item_count = sum(item.quantity for item in order.items)
    estimates = get_fulfillment_estimates(item_count)
    return render_template('confirmation.html', order=order, estimates=estimates, item_count=item_count)

def analyze_order_stepper(order):
    """
    Determine dynamic stepper configuration based on items ordered:
    - 'pizza': 4 steps (Received -> Preparing -> Stone Oven -> Ready)
    - 'kitchen_prep': 3 steps (Received -> Kitchen Prep -> Ready) (e.g. Salads, Apps, Desserts)
    - 'beverage_only': 2 steps (Received -> Ready) (e.g. Sodas, Italian sodas, drinks only)
    """
    has_pizza = False
    has_kitchen_prep = False

    for item in order.items:
        cat_slug = ''
        cat_name = ''
        if item.menu_item and item.menu_item.category:
            cat_slug = item.menu_item.category.slug or ''
            cat_name = item.menu_item.category.name or ''
        
        name_lower = (item.item_name or '').lower()
        
        # Check if pizza
        if 'pizza' in cat_slug or 'pizza' in cat_name.lower() or 'pizza' in name_lower or 'margherita' in name_lower or 'calzone' in name_lower or item.crust_option:
            has_pizza = True
        elif 'beverage' in cat_slug or 'beverage' in cat_name.lower() or any(w in name_lower for w in ['soda', 'aranciata', 'water', 'drink', 'beverage', 'cola', 'tea', 'lemonade', 'pellegrino']):
            pass
        else:
            has_kitchen_prep = True

    if has_pizza:
        order_category = 'pizza'
        prep_desc = "Prepping artisan dough, salads & sides" if has_kitchen_prep else "Hand-tossing dough & fresh toppings"
        prep_subtitle = "Our kitchen team is hand-tossing dough and preparing fresh sides." if has_kitchen_prep else "Our kitchen team is hand-tossing the dough and layering fresh toppings."
        steps = [
            {
                'id': 1,
                'name': 'Received',
                'title': '1. Received',
                'desc': 'Order confirmed & queued in kitchen',
                'icon': 'bi-receipt'
            },
            {
                'id': 2,
                'name': 'Preparing',
                'title': '2. Preparing',
                'desc': prep_desc,
                'icon': 'bi-egg-fried'
            },
            {
                'id': 3,
                'name': 'Stone Oven',
                'title': '3. Stone Oven',
                'desc': 'Baking at 700° in deck oven',
                'icon': 'bi-fire'
            },
            {
                'id': 4,
                'name': 'Ready',
                'title': '4. Out for Delivery' if order.order_type == 'delivery' else '4. Ready for Pickup',
                'desc': 'Packaged & out for delivery' if order.order_type == 'delivery' else 'Waiting at front pickup counter',
                'icon': 'bi-bicycle' if order.order_type == 'delivery' else 'bi-bag-check'
            }
        ]
        status_map = {
            'Received': 1,
            'Preparing': 2,
            'Baking': 3,
            'In Oven': 3,
            'Ready': 4,
            'Completed': 5,
            'Cancelled': -1
        }
        bake_subtitle = "Your pizza is baking at 700° in our authentic stone wood-fired deck oven!"
        pickup_estimate = "20 - 25 mins"

    elif has_kitchen_prep:
        order_category = 'kitchen_prep'
        # 3-step stepper (Stone oven omitted!)
        steps = [
            {
                'id': 1,
                'name': 'Received',
                'title': '1. Received',
                'desc': 'Order confirmed & queued in kitchen',
                'icon': 'bi-receipt'
            },
            {
                'id': 2,
                'name': 'Preparing',
                'title': '2. Kitchen Prep',
                'desc': 'Tossing fresh greens & packaging sides',
                'icon': 'bi-egg-fried'
            },
            {
                'id': 3,
                'name': 'Ready',
                'title': '3. Out for Delivery' if order.order_type == 'delivery' else '3. Ready for Pickup',
                'desc': 'Packaged & out for delivery' if order.order_type == 'delivery' else 'Chilled & waiting at pickup counter',
                'icon': 'bi-bicycle' if order.order_type == 'delivery' else 'bi-bag-check'
            }
        ]
        status_map = {
            'Received': 1,
            'Preparing': 2,
            'Baking': 2,
            'In Oven': 2,
            'Ready': 3,
            'Completed': 4,
            'Cancelled': -1
        }
        prep_subtitle = "Our culinary team is tossing fresh greens, assembling sides, and packaging your order."
        bake_subtitle = "Our culinary team is putting the final touches on your dishes."
        pickup_estimate = "10 - 15 mins (Kitchen Prep)"

    else:
        # Beverage only
        order_category = 'beverage_only'
        # 2-step stepper (No dough prep, no stone oven!)
        steps = [
            {
                'id': 1,
                'name': 'Received',
                'title': '1. Received',
                'desc': 'Order confirmed & sent to beverage bar',
                'icon': 'bi-receipt'
            },
            {
                'id': 2,
                'name': 'Ready',
                'title': '2. Out for Delivery' if order.order_type == 'delivery' else '2. Ready for Pickup',
                'desc': 'Chilled & out for delivery' if order.order_type == 'delivery' else 'Chilled & ready at pickup counter',
                'icon': 'bi-bicycle' if order.order_type == 'delivery' else 'bi-cup-straw'
            }
        ]
        status_map = {
            'Received': 1,
            'Preparing': 1,
            'Baking': 1,
            'In Oven': 1,
            'Ready': 2,
            'Completed': 3,
            'Cancelled': -1
        }
        prep_subtitle = "Our team is chilling and packaging your beverages."
        bake_subtitle = "Your cold drinks are ready at the counter!"
        pickup_estimate = "3 - 5 mins (Express Pickup)"

    current_step = status_map.get(order.status, 1)

    return {
        'order_category': order_category,
        'steps': steps,
        'total_steps': len(steps),
        'status_map': status_map,
        'current_step': current_step,
        'prep_subtitle': prep_subtitle,
        'bake_subtitle': bake_subtitle,
        'pickup_estimate': pickup_estimate
    }

@order_bp.route('/track', methods=['GET', 'POST'])
def track_lookup():
    """Order tracker lookup page & session redirection (supports order #, name, phone, email)"""
    matching_orders = []
    search_query = ''

    if request.method == 'POST':
        search_query = request.form.get('search_query', request.form.get('order_number', '')).strip()
        clean_query = search_query.lstrip('#').strip()
        digits_only = re.sub(r'\D', '', clean_query)

        if clean_query:
            # Query by 1) Order Number, 2) Customer Name (case-insensitive), 3) Customer Email, 4) Customer Phone
            filter_conditions = [
                Order.order_number.ilike(f'%{clean_query}%'),
                Order.customer_name.ilike(f'%{clean_query}%'),
                Order.customer_email.ilike(f'%{clean_query}%'),
                Order.customer_phone.ilike(f'%{clean_query}%')
            ]
            if len(digits_only) >= 4:
                # Strip punctuation from phone in SQL for unformatted matching
                clean_phone_sql = db.func.replace(
                    db.func.replace(
                        db.func.replace(
                            db.func.replace(Order.customer_phone, '(', ''),
                            ')', ''
                        ),
                        '-', ''
                    ),
                    ' ', ''
                )
                filter_conditions.append(clean_phone_sql.ilike(f'%{digits_only}%'))
                if len(digits_only) == 10:
                    formatted_phone = f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
                    filter_conditions.append(Order.customer_phone.ilike(f'%{formatted_phone}%'))

            matching_orders = Order.query.filter(db.or_(*filter_conditions)).order_by(Order.id.desc()).all()

            if len(matching_orders) == 1:
                matched_order = matching_orders[0]
                session['active_order_number'] = matched_order.order_number
                session.modified = True
                return redirect(url_for('order.track_order', order_number=matched_order.order_number))
            elif len(matching_orders) > 1:
                flash(f'Found {len(matching_orders)} orders matching "{search_query}". Select your order below to open the live tracker.', 'info')
            else:
                flash(f'No orders found matching "{search_query}". Please verify your order number, name, phone, or email.', 'danger')
        else:
            flash('Please enter an order number, name, phone, or email to find your order.', 'warning')

    # If customer already has an active order in session and didn't ask for a fresh lookup
    active_order_num = session.get('active_order_number')
    if not matching_orders and active_order_num and request.args.get('new') != '1' and request.method == 'GET':
        order = Order.query.filter_by(order_number=active_order_num).first()
        if order:
            return redirect(url_for('order.track_order', order_number=active_order_num))

    return render_template(
        'track_lookup.html',
        active_order_number=active_order_num,
        matching_orders=matching_orders,
        search_query=search_query
    )

@order_bp.route('/<order_number>/track')
def track_order(order_number):
    """Live visual order progress tracker (PB-05 / PB-10: Ayden Lotter)"""
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    session['active_order_number'] = order.order_number
    session.modified = True
    item_count = sum(item.quantity for item in order.items)
    estimates = get_fulfillment_estimates(item_count)
    stepper_config = analyze_order_stepper(order)

    return render_template(
        'track.html',
        order=order,
        estimates=estimates,
        item_count=item_count,
        stepper_config=stepper_config,
        current_step=stepper_config['current_step']
    )

@order_bp.route('/api/<order_number>/status')
def order_status_api(order_number):
    """API endpoint for live order tracking polling (PB-05 / PB-10: Ayden Lotter)"""
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    stepper_config = analyze_order_stepper(order)
    return jsonify({
        'success': True,
        'order_number': order.order_number,
        'status': order.status,
        'order_category': stepper_config['order_category'],
        'current_step': stepper_config['current_step'],
        'total_steps': stepper_config['total_steps'],
        'order_type': order.order_type,
        'customer_name': order.customer_name
    })

