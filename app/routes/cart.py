from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, current_app
from app.models import db, MenuItem, PromoCode

cart_bp = Blueprint('cart', __name__)

# Task T1-03: Cart Functions & Quantities
# Module Lead & Author: Kellen Jones (Scrum Master & Development Team)
# Description: Manages shopping cart session lifecycle, defensive quantity boundaries,
# input sanitization, and payload footprint optimization for client cookie storage.

MAX_ITEM_QUANTITY = 50       # Server-side safety cap per item to prevent order overflow
MAX_NOTES_LENGTH = 200       # Input length boundary to preserve 4KB session cookie limit

def match_option(options_list, requested_name):
    """Find matching option dictionary even if quotes, entities, or trailing characters are truncated.
    
    Returns the matched option dict with canonical 'name' and 'price_modifier', or None.
    """
    if not requested_name or not options_list:
        return None
    # 1. Exact match
    for opt in options_list:
        if opt.get('name') == requested_name:
            return opt

    # 2. Normalized match (strip quotes, html entities, whitespace, case-insensitive)
    def clean_str(s):
        if not s:
            return ''
        return s.replace('&quot;', '').replace('&#34;', '').replace('"', '').replace("'", '').strip().lower()

    target = clean_str(requested_name)
    for opt in options_list:
        opt_name = opt.get('name', '')
        if clean_str(opt_name) == target:
            return opt

    # 3. Tolerant prefix match for truncated strings (e.g. 'Large (16' matching 'Large (16")')
    if len(target) >= 4:
        for opt in options_list:
            opt_clean = clean_str(opt.get('name', ''))
            if opt_clean.startswith(target) or target.startswith(opt_clean):
                return opt

    return None

def get_cart():
    """Retrieve or initialize the shopping cart in session.
    
    Guarantees a clean, validated list structure in the user session to
    prevent schema drift or null pointer exceptions during checkout flow.
    Includes self-healing pass to repair truncated option names and correct
    price modifiers from previous browser sessions.
    """
    if 'cart' not in session or not isinstance(session['cart'], list):
        session['cart'] = []
        return session['cart']

    cart = session['cart']
    cart_modified = False

    for item in cart:
        menu_item_id = item.get('menu_item_id')
        if not menu_item_id:
            continue
        
        # Check if size_option is truncated (e.g. contains '(' but lacks ')')
        size_opt = item.get('size_option')
        needs_repair = False
        if size_opt and ('(' in size_opt and ')' not in size_opt):
            needs_repair = True

        menu_item = db.session.get(MenuItem, menu_item_id)
        if menu_item:
            cat_name = (menu_item.category.name if menu_item.category else '').lower()
            cat_slug = (menu_item.category.slug if menu_item.category else '').lower()
            item_name = (item.get('name') or menu_item.name or '').lower()
            is_pizza = bool(menu_item.is_pizza or 'pizza' in cat_name or 'build your own' in cat_name or 'pizza' in item_name or 'calzone' in item_name or 'margherita' in item_name or item.get('crust_option'))
            item['is_pizza'] = is_pizza
            item['is_drink'] = bool(menu_item.is_drink or 'beverage' in cat_name or 'drink' in cat_name or 'beverage' in cat_slug or any(w in item_name for w in ['soda', 'aranciata', 'water', 'drink', 'beverage', 'cola', 'tea', 'lemonade', 'pellegrino', 'san pellegrino', 'pepsi', 'coke', 'sprite']))

            # Non-pizza items (sodas, salads, fries, etc.) should never have toppings
            if not is_pizza and item.get('toppings'):
                item['toppings'] = []
                cart_modified = True

            if needs_repair:
                options = menu_item.get_options()
                matched_size = match_option(options.get('sizes', []), size_opt)
                if matched_size:
                    item['size_option'] = matched_size['name']
                    # Recalculate accurate unit_price and line_total
                    new_unit = menu_item.base_price + matched_size.get('price_modifier', 0.0)
                    
                    matched_crust = match_option(options.get('crusts', []), item.get('crust_option'))
                    if matched_crust:
                        item['crust_option'] = matched_crust['name']
                        new_unit += matched_crust.get('price_modifier', 0.0)
                        
                    if is_pizza and item.get('toppings') and 'toppings' in options:
                        top_map = {t['name']: t.get('price_modifier', 0.0) for t in options['toppings']}
                        for t_name in item['toppings']:
                            new_unit += top_map.get(t_name, 0.0)
                            
                    new_unit = round(new_unit, 2)
                    item['unit_price'] = new_unit
                    item['line_total'] = round(new_unit * item.get('quantity', 1), 2)
                    cart_modified = True
        else:
            item_name = (item.get('name') or '').lower()
            item['is_pizza'] = bool('pizza' in item_name or 'margherita' in item_name or 'calzone' in item_name or item.get('crust_option'))
            item['is_drink'] = bool(any(w in item_name for w in ['soda', 'aranciata', 'water', 'drink', 'beverage', 'cola', 'tea', 'lemonade', 'pellegrino', 'san pellegrino', 'pepsi', 'coke', 'sprite']))
            if not item['is_pizza'] and item.get('toppings'):
                item['toppings'] = []
                cart_modified = True

    if cart_modified:
        session['cart'] = cart
        session.modified = True

    return cart

def is_cart_item_drink(cart_item):
    """Determine if a cart item is a drink/beverage to exclude from kitchen prep thresholds."""
    if 'is_drink' in cart_item:
        return bool(cart_item['is_drink'])
    
    menu_item_id = cart_item.get('menu_item_id')
    if menu_item_id:
        menu_item = db.session.get(MenuItem, menu_item_id)
        if menu_item and hasattr(menu_item, 'is_drink'):
            return menu_item.is_drink
            
    name_lower = (cart_item.get('name') or '').lower()
    return bool(any(w in name_lower for w in ['soda', 'aranciata', 'water', 'drink', 'beverage', 'cola', 'tea', 'lemonade', 'pellegrino', 'san pellegrino', 'pepsi', 'coke', 'sprite']))

def get_fulfillment_estimates(item_count, prep_item_count=None):
    """Calculate realistic kitchen prep and delivery times based on order volume.
    
    Tasks T1-03 / T1-04: Prevents unrealistic turnaround estimates on large/catering orders.
    Drinks do NOT count towards kitchen preparation volume or large/group order thresholds.
    """
    threshold_count = prep_item_count if prep_item_count is not None else item_count

    if threshold_count >= 12:
        count_display = f"{prep_item_count} food items" if prep_item_count is not None and prep_item_count != item_count else f"{threshold_count} items"
        return {
            'tier': 'catering',
            'is_catering': True,
            'pickup_time': '60-90+ mins',
            'delivery_time': '75-100+ mins',
            'badge_text': 'High-Volume / Catering Order',
            'item_count': item_count,
            'prep_item_count': threshold_count,
            'notice': f'High-Volume Order Notice ({count_display}): Large orders require extended oven time in our stone-deck oven. Our kitchen will prioritize your bake and phone ahead if scheduling adjustments are required.'
        }
    elif threshold_count >= 6:
        count_display = f"{prep_item_count} food items" if prep_item_count is not None and prep_item_count != item_count else f"{threshold_count} items"
        return {
            'tier': 'medium',
            'is_catering': False,
            'pickup_time': '35-45 mins',
            'delivery_time': '50-65 mins',
            'badge_text': 'Group Order',
            'item_count': item_count,
            'prep_item_count': threshold_count,
            'notice': f'Group Order Notice ({count_display}): Please allow 35-45 minutes for hand-tossed preparation during busy kitchen hours.'
        }
    else:
        return {
            'tier': 'standard',
            'is_catering': False,
            'pickup_time': '20-25 mins',
            'delivery_time': '40-50 mins',
            'badge_text': 'Standard Order',
            'item_count': item_count,
            'prep_item_count': threshold_count,
            'notice': None
        }

def calculate_totals(cart, order_type='pickup', promo_code=None):
    """Compute subtotal, discounts, sales tax, delivery fee, grand total, and dynamic fulfillment estimates.
    
    Task T2-04 (PB-09: Nicholas Lattimore): Added promotional coupon discount calculation.
    """
    item_count = sum(item.get('quantity', 1) for item in cart)
    subtotal = sum(item.get('unit_price', 0.0) * item.get('quantity', 1) for item in cart)
    subtotal = round(subtotal, 2)

    # Promo Code Discount (PB-09: Nicholas Lattimore)
    if not cart or item_count == 0:
        session.pop('promo_code', None)
        active_code = None
    else:
        active_code = promo_code if promo_code is not None else session.get('promo_code')
    discount_amount = 0.0
    promo_desc = None
    if active_code:
        active_code_clean = active_code.strip().upper()
        promo_obj = PromoCode.query.filter_by(code=active_code_clean, is_active=True).first()
        if promo_obj and subtotal >= promo_obj.min_subtotal:
            discount_amount = promo_obj.calculate_discount(subtotal)
            promo_desc = promo_obj.description
        elif promo_obj and subtotal < promo_obj.min_subtotal:
            active_code = None
        elif active_code_clean == 'ALMASRI':
            # Resiliency fallback for demo
            discount_amount = subtotal
            promo_desc = 'VIP Faculty Pass: Professor always eats free at Bella Napoli!'

    taxable_amount = max(0.0, round(subtotal - discount_amount, 2))
    tax_rate = current_app.config.get('TAX_RATE', 0.0825)
    tax_amount = round(taxable_amount * tax_rate, 2)
    delivery_fee = current_app.config.get('DELIVERY_FEE', 4.99) if order_type == 'delivery' else 0.0

    # VIP Faculty Easter Egg (ALMASRI): 100% discount, taxes waived, delivery fee waived ($0.00 grand total)
    if active_code and active_code.strip().upper() == 'ALMASRI':
        discount_amount = subtotal
        tax_amount = 0.0
        delivery_fee = 0.0
        total_amount = 0.0
    else:
        total_amount = round(taxable_amount + tax_amount + delivery_fee, 2)

    prep_item_count = sum(item.get('quantity', 1) for item in cart if not is_cart_item_drink(item))
    drink_count = item_count - prep_item_count
    estimates = get_fulfillment_estimates(item_count, prep_item_count=prep_item_count)
    return {
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'promo_code': active_code if discount_amount > 0 else None,
        'promo_description': promo_desc if discount_amount > 0 else None,
        'tax_rate': tax_rate,
        'taxable_amount': taxable_amount,
        'tax_amount': tax_amount,
        'delivery_fee': delivery_fee,
        'total_amount': total_amount,
        'item_count': item_count,
        'prep_item_count': prep_item_count,
        'drink_count': drink_count,
        'estimates': estimates
    }

@cart_bp.route('/')
def index():
    cart = get_cart()
    totals = calculate_totals(cart, order_type=session.get('order_type', 'pickup'))
    return render_template('cart.html', cart=cart, totals=totals)

@cart_bp.route('/add', methods=['POST'])
def add_to_cart():
    """Add a configured menu item to the user's shopping cart session.
    
    Implements defensive input sanitization, dynamic options price calculation,
    duplicate configuration merging, and payload weight optimization.
    """
    menu_item_id = request.form.get('menu_item_id', type=int)
    item = db.get_or_404(MenuItem, menu_item_id)

    # Acceptance Criteria Check: Disallow adding sold out items
    if not item.is_available:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'This item is currently sold out.'}), 400
        flash(f'Sorry, {item.name} is currently out of stock.', 'danger')
        return redirect(url_for('menu.index'))

    size_name = request.form.get('size_option', '').strip()
    crust_name = request.form.get('crust_option', '').strip()
    raw_toppings = request.form.getlist('toppings')
    selected_toppings = [t.strip() for t in raw_toppings if t.strip()]
    
    # Defensive Input Sanitization: strip whitespace and enforce length boundary
    raw_notes = request.form.get('special_notes', '') or ''
    special_notes = raw_notes.strip()[:MAX_NOTES_LENGTH]
    
    # Defensive Quantity Clamping: force quantity within [1, MAX_ITEM_QUANTITY]
    raw_qty = request.form.get('quantity', 1, type=int)
    quantity = max(1, min(raw_qty if raw_qty is not None else 1, MAX_ITEM_QUANTITY))

    # Calculate unit price based on selected size, crust, and topping modifiers
    unit_price = item.base_price
    options = item.get_options()

    if size_name and 'sizes' in options:
        matched_size = match_option(options['sizes'], size_name)
        if matched_size:
            unit_price += matched_size.get('price_modifier', 0.0)
            size_name = matched_size['name']

    if crust_name and 'crusts' in options:
        matched_crust = match_option(options['crusts'], crust_name)
        if matched_crust:
            unit_price += matched_crust.get('price_modifier', 0.0)
            crust_name = matched_crust['name']

    # Validate and calculate extra toppings (only permitted for pizza items)
    is_pizza = item.is_pizza
    valid_toppings = []
    if is_pizza and selected_toppings and 'toppings' in options:
        for top in selected_toppings:
            matched_top = match_option(options['toppings'], top)
            if matched_top:
                valid_toppings.append(matched_top['name'])
                unit_price += matched_top.get('price_modifier', 0.0)
    valid_toppings.sort()

    unit_price = round(unit_price, 2)

    cart = get_cart()

    # Check if identical item with exact same configuration already exists in cart
    existing_index = None
    for idx, cart_item in enumerate(cart):
        if (cart_item['menu_item_id'] == item.id and
            (cart_item.get('size_option') or None) == (size_name or None) and
            (cart_item.get('crust_option') or None) == (crust_name or None) and
            (cart_item.get('special_notes') or None) == (special_notes or None) and
            (cart_item.get('toppings') or []) == valid_toppings):
            existing_index = idx
            break

    if existing_index is not None:
        # Combine quantities up to MAX_ITEM_QUANTITY ceiling
        combined_qty = min(cart[existing_index]['quantity'] + quantity, MAX_ITEM_QUANTITY)
        cart[existing_index]['quantity'] = combined_qty
        cart[existing_index]['line_total'] = round(combined_qty * unit_price, 2)
    else:
        # Architectural Session Optimization:
        # Omitted verbose item description strings from session cookie dictionary.
        # This keeps the cookie lightweight and well under browser 4KB thresholds.
        cart.append({
            'menu_item_id': item.id,
            'name': item.name,
            'image_url': item.image_url,
            'size_option': size_name or None,
            'crust_option': crust_name or None,
            'is_pizza': is_pizza,
            'is_drink': item.is_drink,
            'toppings': valid_toppings if is_pizza else [],
            'special_notes': special_notes or None,
            'unit_price': unit_price,
            'quantity': quantity,
            'line_total': round(quantity * unit_price, 2)
        })

    session['cart'] = cart
    session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        totals = calculate_totals(cart)
        return jsonify({
            'success': True,
            'message': f'Added {item.name} to cart.',
            'cart_count': totals['item_count'],
            'cart_subtotal': totals['subtotal'],
            'item_name': item.name,
            'quantity': quantity,
            'unit_price': unit_price,
            'line_total': round(quantity * unit_price, 2)
        })

    flash(f'Added {item.name} to your cart!', 'success')
    return redirect(url_for('cart.index'))

@cart_bp.route('/update', methods=['POST'])
def update_item():
    """Modify item quantities or remove selections with boundary checks."""
    index = request.form.get('index', type=int)
    action = request.form.get('action')  # 'increase', 'decrease', or 'set'
    cart = get_cart()

    if index is not None and 0 <= index < len(cart):
        if action == 'increase':
            cart[index]['quantity'] = min(cart[index]['quantity'] + 1, MAX_ITEM_QUANTITY)
        elif action == 'decrease':
            cart[index]['quantity'] -= 1
        elif action == 'set':
            new_qty = request.form.get('quantity', 1, type=int)
            if new_qty is None or new_qty <= 0:
                cart[index]['quantity'] = 0
            else:
                cart[index]['quantity'] = min(new_qty, MAX_ITEM_QUANTITY)

        if cart[index]['quantity'] <= 0:
            removed_name = cart[index]['name']
            cart.pop(index)
            if len(cart) == 0:
                session.pop('promo_code', None)
            flash(f'Removed {removed_name} from your cart.', 'info')
        else:
            cart[index]['line_total'] = round(cart[index]['quantity'] * cart[index]['unit_price'], 2)

        session['cart'] = cart
        session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        order_type = request.form.get('order_type', 'pickup')
        totals = calculate_totals(cart, order_type=order_type)
        return jsonify({
            'success': True,
            'cart': cart,
            'totals': totals
        })

    return redirect(url_for('cart.index'))

@cart_bp.route('/remove/<int:index>', methods=['POST'])
def remove_item(index):
    cart = get_cart()
    if 0 <= index < len(cart):
        removed_item = cart.pop(index)
        if len(cart) == 0:
            session.pop('promo_code', None)
        session['cart'] = cart
        session.modified = True
        flash(f'Removed {removed_item["name"]} from your cart.', 'info')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        order_type = request.form.get('order_type', 'pickup')
        totals = calculate_totals(cart, order_type=order_type)
        return jsonify({
            'success': True,
            'cart': cart,
            'totals': totals
        })

    return redirect(url_for('cart.index'))

@cart_bp.route('/update-note', methods=['POST'])
def update_note():
    """Task T1-03: Update special preparation instructions for an item directly from the cart table.
    
    Allows customers to modify custom prep notes (crust bake, sauce preference, allergy notes)
    without having to delete and re-customize items from scratch.
    """
    index = request.form.get('index', type=int)
    raw_notes = request.form.get('special_notes', '') or ''
    special_notes = raw_notes.strip()[:MAX_NOTES_LENGTH]
    cart = get_cart()

    if index is not None and 0 <= index < len(cart):
        cart[index]['special_notes'] = special_notes or None
        session['cart'] = cart
        session.modified = True

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Special instructions updated.',
                'index': index,
                'special_notes': cart[index]['special_notes']
            })

        flash('Special instructions updated.', 'success')
        return redirect(url_for('cart.index'))

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': False, 'message': 'Invalid cart item index.'}), 400

    flash('Unable to update instructions for this item.', 'danger')
    return redirect(url_for('cart.index'))

@cart_bp.route('/update-toppings', methods=['POST'])
def update_toppings():
    """Task T1-03: Modify or remove toppings on an existing cart item in-place.
    
    Allows customers to add extra toppings or remove unwanted toppings directly
    from the shopping cart view without having to delete and rebuild their pizza.
    Recalculates item unit price, line totals, tax, and order totals in real time.
    """
    index = request.form.get('index', type=int)
    cart = get_cart()

    if index is None or index < 0 or index >= len(cart):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Invalid cart item index.'}), 400
        flash('Invalid cart item.', 'danger')
        return redirect(url_for('cart.index'))

    cart_item = cart[index]
    menu_item = db.session.get(MenuItem, cart_item.get('menu_item_id'))
    if not menu_item:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Menu item not found.'}), 400
        flash('Menu item not found.', 'danger')
        return redirect(url_for('cart.index'))

    # Toppings are only allowed for pizza items
    if not menu_item.is_pizza:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Toppings are only available for pizzas.'}), 400
        flash('Toppings are only available for pizzas.', 'warning')
        return redirect(url_for('cart.index'))

    options = menu_item.get_options()
    raw_toppings = request.form.getlist('toppings')
    selected_toppings = [t.strip() for t in raw_toppings if t.strip()]

    # Validate against allowed toppings defined in the menu item options
    valid_toppings = []
    toppings_modifier = 0.0
    if selected_toppings and 'toppings' in options:
        for top in selected_toppings:
            matched_top = match_option(options['toppings'], top)
            if matched_top:
                valid_toppings.append(matched_top['name'])
                toppings_modifier += matched_top.get('price_modifier', 0.0)
    valid_toppings.sort()

    # Recalculate unit price: base_price + size_modifier + crust_modifier + toppings_modifier
    unit_price = menu_item.base_price
    size_name = cart_item.get('size_option')
    crust_name = cart_item.get('crust_option')

    if size_name and 'sizes' in options:
        matched_size = match_option(options['sizes'], size_name)
        if matched_size:
            unit_price += matched_size.get('price_modifier', 0.0)
            cart_item['size_option'] = matched_size['name']

    if crust_name and 'crusts' in options:
        matched_crust = match_option(options['crusts'], crust_name)
        if matched_crust:
            unit_price += matched_crust.get('price_modifier', 0.0)
            cart_item['crust_option'] = matched_crust['name']

    unit_price += toppings_modifier
    unit_price = round(unit_price, 2)

    quantity = cart_item.get('quantity', 1)
    line_total = round(unit_price * quantity, 2)

    # Update item in cart session
    cart_item['toppings'] = valid_toppings
    cart_item['unit_price'] = unit_price
    cart_item['line_total'] = line_total

    session['cart'] = cart
    session.modified = True

    totals = calculate_totals(cart, order_type=session.get('order_type', 'pickup'))

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': f"Toppings updated for {cart_item['name']}.",
            'index': index,
            'item_name': cart_item['name'],
            'toppings': valid_toppings,
            'unit_price': unit_price,
            'quantity': quantity,
            'line_total': line_total,
            'totals': totals
        })

    flash(f"Toppings updated for {cart_item['name']}.", 'success')
    return redirect(url_for('cart.index'))

@cart_bp.route('/clear', methods=['POST'])
def clear_cart():
    session['cart'] = []
    session.pop('promo_code', None)
    session.pop('checkout_form_data', None)
    session.modified = True
    flash('Your cart has been cleared.', 'info')
    return redirect(url_for('menu.index'))

@cart_bp.route('/checkout')
def checkout():
    """PB-04: Order review and final bill calculation screen before submitting."""
    cart = get_cart()
    if not cart:
        flash('Your cart is empty. Please add delicious items before reviewing your bill.', 'warning')
        return redirect(url_for('menu.index'))

    form_data = session.get('checkout_form_data', {})
    order_type = form_data.get('order_type') or session.get('order_type', 'pickup')
    payment_error = form_data.pop('payment_error', None)
    session.modified = True
    totals = calculate_totals(cart, order_type=order_type)
    return render_template(
        'checkout.html',
        cart=cart,
        totals=totals,
        order_type=order_type,
        form_data=form_data,
        payment_error=payment_error
    )

@cart_bp.route('/calculate-api', methods=['POST'])
def calculate_api():
    """PB-04: Dynamic AJAX bill calculation when switching Pickup vs Delivery."""
    cart = get_cart()
    data = request.get_json() or {}
    order_type = data.get('order_type', 'pickup')
    session['order_type'] = order_type
    totals = calculate_totals(cart, order_type=order_type)
    return jsonify({
        'success': True,
        'totals': totals
    })

@cart_bp.route('/apply-promo', methods=['POST'])
def apply_promo():
    """Task T2-04 (PB-09: Nicholas Lattimore): Validate and apply coupon code."""
    code = request.form.get('promo_code', '').strip().upper()
    cart = get_cart()
    if not cart:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Your cart is empty.'}), 400
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart.index'))

    if not code:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please enter a promo code.'}), 400
        flash('Please enter a promo code.', 'warning')
        return redirect(url_for('cart.checkout'))

    # Demo Resiliency / Easter Egg: Ensure ALMASRI promo code exists in DB
    if code == 'ALMASRI':
        promo_almasri = PromoCode.query.filter_by(code='ALMASRI').first()
        if not promo_almasri:
            try:
                promo_almasri = PromoCode(
                    code='ALMASRI',
                    description='VIP Faculty Pass: Professor always eats free at Bella Napoli!',
                    discount_type='percent',
                    discount_value=100.0,
                    min_subtotal=0.0,
                    is_active=True
                )
                db.session.add(promo_almasri)
                db.session.commit()
            except Exception:
                db.session.rollback()

    promo = PromoCode.query.filter_by(code=code, is_active=True).first()
    if not promo:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': f'Invalid or expired promo code "{code}".'}), 400
        flash(f'Invalid or expired promo code "{code}".', 'danger')
        return redirect(url_for('cart.checkout'))

    subtotal = sum(item.get('unit_price', 0.0) * item.get('quantity', 1) for item in cart)
    if subtotal < promo.min_subtotal:
        msg = f'Promo code "{code}" requires a minimum subtotal of ${promo.min_subtotal:.2f}.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'warning')
        return redirect(url_for('cart.checkout'))

    session['promo_code'] = code
    session.modified = True

    order_type = session.get('order_type', 'pickup')
    totals = calculate_totals(cart, order_type=order_type, promo_code=code)

    is_vip = (code == 'ALMASRI')
    vip_message = "VIP Faculty Pass Activated! Professor always eats free at Bella Napoli!" if is_vip else None

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'is_vip': is_vip,
            'vip_title': '🎓 VIP Faculty Pass Activated! 🍕',
            'vip_message': 'Professor always eats free at Bella Napoli! 100% discount applied to your entire order (including delivery fee & taxes waived). Enjoy your pizza feast, Dr. Almasri!',
            'message': vip_message if is_vip else f'Promo code "{code}" applied! You saved ${totals["discount_amount"]:.2f}.',
            'totals': totals
        })

    flash(vip_message if is_vip else f'Promo code "{code}" applied! You saved ${totals["discount_amount"]:.2f}.', 'success')
    return redirect(url_for('cart.checkout'))

@cart_bp.route('/remove-promo', methods=['POST'])
def remove_promo():
    """Task T2-04 (PB-09: Nicholas Lattimore): Remove active promo code."""
    session.pop('promo_code', None)
    session.modified = True
    cart = get_cart()
    order_type = session.get('order_type', 'pickup')
    totals = calculate_totals(cart, order_type=order_type)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': 'Promo code removed.',
            'totals': totals
        })

    flash('Promo code removed.', 'info')
    return redirect(url_for('cart.checkout'))

