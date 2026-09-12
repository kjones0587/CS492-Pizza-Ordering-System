from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, current_app
from app.models import db, MenuItem

cart_bp = Blueprint('cart', __name__)

# Task T1-03: Cart Functions & Quantities
# Module Lead & Author: Kellen Jones (Scrum Master & Development Team)
# Description: Manages shopping cart session lifecycle, defensive quantity boundaries,
# input sanitization, and payload footprint optimization for client cookie storage.

MAX_ITEM_QUANTITY = 50       # Server-side safety cap per item to prevent order overflow
MAX_NOTES_LENGTH = 200       # Input length boundary to preserve 4KB session cookie limit

def get_cart():
    """Retrieve or initialize the shopping cart in session.
    
    Guarantees a clean, validated list structure in the user session to
    prevent schema drift or null pointer exceptions during checkout flow.
    """
    if 'cart' not in session or not isinstance(session['cart'], list):
        session['cart'] = []
    return session['cart']

def get_fulfillment_estimates(item_count):
    """Calculate realistic kitchen prep and delivery times based on order volume.
    
    Tasks T1-03 / T1-04: Prevents unrealistic turnaround estimates on large/catering orders.
    """
    if item_count >= 12:
        return {
            'tier': 'catering',
            'is_catering': True,
            'pickup_time': '60-90+ mins',
            'delivery_time': '75-100+ mins',
            'badge_text': 'High-Volume / Catering Order',
            'notice': f'High-Volume Order Notice ({item_count} items): Large orders require extended oven time in our stone-deck oven. Our kitchen will prioritize your bake and phone ahead if scheduling adjustments are required.'
        }
    elif item_count >= 6:
        return {
            'tier': 'medium',
            'is_catering': False,
            'pickup_time': '35-45 mins',
            'delivery_time': '50-65 mins',
            'badge_text': 'Group Order',
            'notice': f'Group Order Notice ({item_count} items): Please allow 35-45 minutes for hand-tossed preparation during busy kitchen hours.'
        }
    else:
        return {
            'tier': 'standard',
            'is_catering': False,
            'pickup_time': '20-25 mins',
            'delivery_time': '40-50 mins',
            'badge_text': 'Standard Order',
            'notice': None
        }

def calculate_totals(cart, order_type='pickup'):
    """Compute subtotal, sales tax, delivery fee, grand total, and dynamic fulfillment estimates."""
    item_count = sum(item.get('quantity', 1) for item in cart)
    subtotal = sum(item.get('unit_price', 0.0) * item.get('quantity', 1) for item in cart)
    subtotal = round(subtotal, 2)
    tax_rate = current_app.config.get('TAX_RATE', 0.0825)
    tax_amount = round(subtotal * tax_rate, 2)
    delivery_fee = current_app.config.get('DELIVERY_FEE', 4.99) if order_type == 'delivery' else 0.0
    total_amount = round(subtotal + tax_amount + delivery_fee, 2)
    estimates = get_fulfillment_estimates(item_count)
    return {
        'subtotal': subtotal,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'delivery_fee': delivery_fee,
        'total_amount': total_amount,
        'item_count': item_count,
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
        for s in options['sizes']:
            if s['name'] == size_name:
                unit_price += s.get('price_modifier', 0.0)
                break

    if crust_name and 'crusts' in options:
        for c in options['crusts']:
            if c['name'] == crust_name:
                unit_price += c.get('price_modifier', 0.0)
                break

    # Validate and calculate extra toppings
    valid_toppings = []
    if selected_toppings and 'toppings' in options:
        toppings_map = {t['name']: t.get('price_modifier', 0.0) for t in options['toppings']}
        for top in selected_toppings:
            if top in toppings_map:
                valid_toppings.append(top)
                unit_price += toppings_map[top]
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
            'toppings': valid_toppings,
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

@cart_bp.route('/clear', methods=['POST'])
def clear_cart():
    session['cart'] = []
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

    order_type = session.get('order_type', 'pickup')
    totals = calculate_totals(cart, order_type=order_type)
    return render_template('checkout.html', cart=cart, totals=totals, order_type=order_type)

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
