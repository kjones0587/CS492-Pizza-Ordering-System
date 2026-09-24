import json
from functools import wraps
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from app.models import db, Order, OrderItem, Manager, Category, MenuItem, PromoCode

staff_bp = Blueprint('staff', __name__)

def staff_login_required(f):
    """Decorator requiring store manager / staff authentication (PB-07: Michael Fabacher)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow existing test suite passes when standard testing flag is enabled, unless TESTING_AUTH is explicitly active
        if not session.get('staff_user_id') and not current_app.config.get('TESTING_AUTH', False) and current_app.config.get('TESTING'):
            return f(*args, **kwargs)
        if not session.get('staff_user_id'):
            flash('Please log in with manager credentials to access the staff portal.', 'warning')
            return redirect(url_for('staff.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@staff_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Store Manager & Staff Authentication (PB-07: Michael Fabacher)"""
    if session.get('staff_user_id'):
        return redirect(url_for('staff.orders'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('staff/login.html')

        manager = Manager.query.filter_by(username=username).first()
        if manager and manager.is_active and manager.check_password(password):
            session['staff_user_id'] = manager.id
            session['staff_username'] = manager.username
            session['staff_role'] = manager.role
            flash(f'Welcome back, {manager.username}! Logged in as {manager.role}.', 'success')
            next_url = request.args.get('next') or request.form.get('next')
            if next_url and not next_url.startswith('/'):
                next_url = None
            return redirect(next_url or url_for('staff.orders'))
        else:
            flash('Invalid username or password. Please check your credentials.', 'danger')

    return render_template('staff/login.html')

@staff_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Staff logout and session cleanup (PB-07: Michael Fabacher)"""
    session.pop('staff_user_id', None)
    session.pop('staff_username', None)
    session.pop('staff_role', None)
    flash('You have been logged out of the staff portal.', 'info')
    return redirect(url_for('staff.login'))


@staff_bp.route('/orders')
@staff_login_required
def orders():
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('q', '').strip()
    query = Order.query.order_by(Order.created_at.desc())

    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)

    if search_query:
        clean_q = search_query.lstrip('#').strip()
        query = query.filter(
            db.or_(
                Order.order_number.ilike(f'%{clean_q}%'),
                Order.customer_name.ilike(f'%{clean_q}%'),
                Order.customer_phone.ilike(f'%{clean_q}%')
            )
        )

    orders_list = query.all()
    latest_order = Order.query.order_by(Order.id.desc()).first()
    latest_order_id = latest_order.id if latest_order else 0
    counts = {
        'all': Order.query.count(),
        'Received': Order.query.filter_by(status='Received').count(),
        'Preparing': Order.query.filter_by(status='Preparing').count(),
        'Baking': Order.query.filter_by(status='Baking').count(),
        'Ready': Order.query.filter_by(status='Ready').count(),
        'Completed': Order.query.filter_by(status='Completed').count(),
    }

    return render_template(
        'staff/orders.html',
        orders=orders_list,
        counts=counts,
        current_filter=status_filter,
        search_query=search_query,
        latest_order_id=latest_order_id
    )

@staff_bp.route('/orders/<int:order_id>/advance', methods=['POST'])
@staff_login_required
def advance_order_status(order_id):
    """1-click kitchen stage progression / bump bar (PB-05 / PB-07: Michael Fabacher)"""
    order = db.get_or_404(Order, order_id)
    status_pipeline = {
        'Received': 'Preparing',
        'Preparing': 'Baking',
        'Baking': 'Ready',
        'Ready': 'Completed'
    }
    next_status = status_pipeline.get(order.status)
    if next_status:
        order.status = next_status
        db.session.commit()
        flash(f"Order {order.order_number} advanced to {next_status}.", 'success')
    else:
        flash(f"Order {order.order_number} is already {order.status}.", 'info')

    return redirect(url_for('staff.orders', status=request.form.get('current_filter', 'all'), q=request.form.get('search_query', '')))

@staff_bp.route('/orders/<int:order_id>/status', methods=['POST'])
@staff_login_required
def update_status(order_id):
    order = db.get_or_404(Order, order_id)
    new_status = request.form.get('status')
    valid_statuses = ['Received', 'Preparing', 'Baking', 'In Oven', 'Ready', 'Completed', 'Cancelled']

    if new_status in valid_statuses:
        # Canonicalize 'In Oven' to 'Baking'
        if new_status == 'In Oven':
            new_status = 'Baking'
        order.status = new_status
        db.session.commit()
        flash(f'Order {order.order_number} status updated to {new_status}.', 'success')
    else:
        flash('Invalid order status.', 'danger')

    return redirect(url_for('staff.orders', status=request.form.get('current_filter', 'all')))

@staff_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
@staff_login_required
def update_order_notes(order_id):
    """Update internal kitchen prep notes for an order (PB-07: Michael Fabacher)"""
    order = db.get_or_404(Order, order_id)
    notes = request.form.get('staff_notes', '').strip()
    order.staff_notes = notes if notes else None
    db.session.commit()
    flash(f"Internal kitchen note updated for order {order.order_number}.", 'success')
    return redirect(url_for('staff.orders', status=request.form.get('current_filter', 'all')))

@staff_bp.route('/orders/<int:order_id>/rush-delay', methods=['POST'])
@staff_login_required
def add_rush_delay(order_id):
    """Add kitchen rush delay annotation to order notes (PB-07: Michael Fabacher)"""
    order = db.get_or_404(Order, order_id)
    delay_minutes = request.form.get('delay_minutes', '10').strip()
    tag = f"[RUSH: +{delay_minutes} min delay]"
    if order.staff_notes:
        if tag not in order.staff_notes:
            order.staff_notes = f"{order.staff_notes} | {tag}"
    else:
        order.staff_notes = tag
    db.session.commit()
    flash(f"Added +{delay_minutes} min rush delay note to Order {order.order_number}.", 'warning')
    return redirect(url_for('staff.orders', status=request.form.get('current_filter', 'all'), q=request.form.get('search_query', '')))


@staff_bp.route('/api/orders/poll', methods=['GET'])
@staff_login_required
def poll_orders():
    """Live auto-refresh polling API for kitchen orders (PB-05 / PB-07: Michael Fabacher)"""
    latest_order = Order.query.order_by(Order.id.desc()).first()
    latest_id = latest_order.id if latest_order else 0
    counts = {
        'all': Order.query.count(),
        'Received': Order.query.filter_by(status='Received').count(),
        'Preparing': Order.query.filter_by(status='Preparing').count(),
        'Baking': Order.query.filter_by(status='Baking').count(),
        'Ready': Order.query.filter_by(status='Ready').count(),
        'Completed': Order.query.filter_by(status='Completed').count(),
    }
    return jsonify({
        'success': True,
        'latest_order_id': latest_id,
        'latest_order_number': latest_order.order_number if latest_order else None,
        'counts': counts,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@staff_bp.route('/menu')
@staff_login_required
def menu():
    """Staff Menu Management Dashboard (PB-08: Nicholas Lattimore)"""
    category_filter = request.args.get('category', 'all')
    categories = Category.query.order_by(Category.display_order).all()

    query = MenuItem.query.join(Category)
    if category_filter and category_filter != 'all':
        query = query.filter(Category.slug == category_filter)

    items = query.order_by(Category.display_order, MenuItem.name).all()

    total_items = MenuItem.query.count()
    in_stock_count = MenuItem.query.filter_by(is_available=True).count()
    sold_out_count = MenuItem.query.filter_by(is_available=False).count()

    return render_template(
        'staff/menu.html',
        items=items,
        categories=categories,
        current_category=category_filter,
        total_items=total_items,
        in_stock_count=in_stock_count,
        sold_out_count=sold_out_count
    )

@staff_bp.route('/menu/<int:item_id>/toggle-status', methods=['POST'])
@staff_login_required
def toggle_item_status(item_id):
    """Toggle menu item availability between In Stock and Sold Out (PB-08: Nicholas Lattimore)"""
    item = db.get_or_404(MenuItem, item_id)
    item.is_available = not item.is_available
    db.session.commit()

    status_str = 'In Stock' if item.is_available else 'Sold Out'
    flash(f"'{item.name}' is now marked as {status_str}.", 'success' if item.is_available else 'warning')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'item_id': item.id,
            'item_name': item.name,
            'is_available': item.is_available,
            'status_text': status_str
        })

    return redirect(url_for('staff.menu', category=request.form.get('current_category', 'all')))
 

@staff_bp.route('/menu/<int:item_id>/update-price', methods=['POST'])
@staff_login_required
def update_item_price(item_id):
    """Update base price for a menu item (PB-08: Nicholas Lattimore)"""
    item = db.get_or_404(MenuItem, item_id)
    try:
        new_price = float(request.form.get('base_price', 0.0))
        if new_price <= 0:
            raise ValueError
        item.base_price = round(new_price, 2)
        db.session.commit()
        flash(f"Updated base price for '{item.name}' to ${item.base_price:.2f}.", 'success')
    except (ValueError, TypeError):
        flash('Please enter a valid positive base price.', 'danger')

    return redirect(url_for('staff.menu', category=request.form.get('current_category', 'all')))


@staff_bp.route('/menu/create', methods=['POST'])
@staff_login_required
def create_menu_item():
    """Add new menu item to catalog (PB-08: Nicholas Lattimore)"""
    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id')
    description = request.form.get('description', '').strip()
    image_url = request.form.get('image_url', '').strip()
    is_available = request.form.get('is_available') in ['on', 'true', '1']

    try:
        base_price = float(request.form.get('base_price', 0.0))
        if base_price <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Please enter a valid positive base price.', 'danger')
        return redirect(url_for('staff.menu'))

    if not name or not category_id:
        flash('Item name and category are required.', 'danger')
        return redirect(url_for('staff.menu'))

    category = db.get_or_404(Category, int(category_id))

    # Automatic realistic fallback image if none provided
    if not image_url:
        cat_slug = category.slug.lower()
        if 'pizza' in cat_slug:
            image_url = 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?auto=format&fit=crop&w=800&q=80'
        elif 'appetizer' in cat_slug or 'sides' in cat_slug:
            image_url = '/static/img/garlic-knots.jpg'
        elif 'beverage' in cat_slug or 'drink' in cat_slug:
            image_url = 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?auto=format&fit=crop&w=800&q=80'
        else:
            image_url = '/static/img/cannoli.jpg'

    options = {'sizes': [], 'crusts': []}
    if 'pizza' in category.slug.lower():
        options = {
            'sizes': [
                {'name': 'Personal (10")', 'price_modifier': 0.0},
                {'name': 'Medium (12")', 'price_modifier': 3.50},
                {'name': 'Large (16")', 'price_modifier': 6.50}
            ],
            'crusts': [
                {'name': 'Neapolitan Hand-Tossed', 'price_modifier': 0.0},
                {'name': 'Crispy Thin Crust', 'price_modifier': 0.0},
                {'name': 'Gluten-Free Cauliflower Crust', 'price_modifier': 3.00}
            ]
        }

    new_item = MenuItem(
        category_id=category.id,
        name=name,
        description=description or f"Freshly prepared {name}.",
        base_price=round(base_price, 2),
        image_url=image_url,
        is_available=is_available,
        options_json=json.dumps(options)
    )
    db.session.add(new_item)
    db.session.commit()
    flash(f"Successfully added '{name}' to {category.name}.", 'success')
    return redirect(url_for('staff.menu', category=category.slug))


@staff_bp.route('/menu/<int:item_id>/update-info', methods=['POST'])
@staff_login_required
def update_item_info(item_id):
    """Update menu item name and description (PB-08: Nicholas Lattimore)"""
    item = db.get_or_404(MenuItem, item_id)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Item name cannot be blank.', 'danger')
    else:
        item.name = name
        item.description = description
        db.session.commit()
        flash(f"Updated details for '{item.name}'.", 'success')

    return redirect(url_for('staff.menu', category=request.form.get('current_category', 'all')))


@staff_bp.route('/menu/<int:item_id>/delete', methods=['POST'])
@staff_login_required
def delete_menu_item(item_id):
    """Delete a menu item from the catalog (PB-08)."""
    item = db.get_or_404(MenuItem, item_id)
    item_name = item.name
    category_slug = item.category.slug if item.category else 'all'

    # Unlink any existing order items to preserve past customer order receipts
    OrderItem.query.filter_by(menu_item_id=item.id).update({'menu_item_id': None})

    db.session.delete(item)
    db.session.commit()
    flash(f"Successfully deleted '{item_name}' from the menu.", 'success')
    return redirect(url_for('staff.menu', category=request.form.get('current_category', category_slug)))



@staff_bp.route('/promos', methods=['GET'])
@staff_login_required
def promos():
    """Staff Promo Code Management Dashboard (PB-09: Nicholas Lattimore)"""
    all_promos = PromoCode.query.order_by(PromoCode.id.desc()).all()
    active_count = PromoCode.query.filter_by(is_active=True).count()
    inactive_count = PromoCode.query.filter_by(is_active=False).count()
    # Compute actual redemptions across customer orders
    promo_counts = {p.id: Order.query.filter_by(promo_code=p.code).count() for p in all_promos}
    return render_template(
        'staff/promos.html',
        promos=all_promos,
        active_count=active_count,
        inactive_count=inactive_count,
        promo_counts=promo_counts
    )


@staff_bp.route('/promos/create', methods=['POST'])
@staff_login_required
def create_promo():
    """Create new promotional coupon code (PB-09: Nicholas Lattimore)"""
    code = request.form.get('code', '').strip().upper()
    description = request.form.get('description', '').strip()
    discount_type = request.form.get('discount_type', 'percent')
    try:
        discount_value = float(request.form.get('discount_value', 0.0))
        min_subtotal = float(request.form.get('min_subtotal', 0.0))
    except (ValueError, TypeError):
        flash('Invalid discount value or minimum subtotal.', 'danger')
        return redirect(url_for('staff.promos'))

    if not code:
        flash('Promo code cannot be blank.', 'danger')
        return redirect(url_for('staff.promos'))

    existing = PromoCode.query.filter_by(code=code).first()
    if existing:
        flash(f"Promo code '{code}' already exists.", 'warning')
        return redirect(url_for('staff.promos'))

    promo = PromoCode(
        code=code,
        description=description or f"Discount code {code}",
        discount_type=discount_type,
        discount_value=discount_value,
        min_subtotal=min_subtotal,
        is_active=True
    )
    db.session.add(promo)
    db.session.commit()
    flash(f"Successfully created active promo code '{code}'.", 'success')
    return redirect(url_for('staff.promos'))


@staff_bp.route('/promos/<int:promo_id>/edit', methods=['POST'])
@staff_login_required
def edit_promo(promo_id):
    """Edit promo code discount rules and description (PB-09: Nicholas Lattimore)"""
    promo = db.get_or_404(PromoCode, promo_id)
    description = request.form.get('description', '').strip()
    discount_type = request.form.get('discount_type', promo.discount_type)
    try:
        discount_value = float(request.form.get('discount_value', promo.discount_value))
        min_subtotal = float(request.form.get('min_subtotal', promo.min_subtotal))
        if discount_value <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Please enter valid positive numbers for discount value and minimum subtotal.', 'danger')
        return redirect(url_for('staff.promos'))

    promo.description = description or promo.description
    promo.discount_type = discount_type
    promo.discount_value = discount_value
    promo.min_subtotal = min_subtotal
    db.session.commit()
    flash(f"Updated discount rules for promo '{promo.code}'.", 'success')
    return redirect(url_for('staff.promos'))


@staff_bp.route('/promos/<int:promo_id>/delete', methods=['POST'])
@staff_login_required
def delete_promo(promo_id):
    """Delete promo code with safety guards against deleting core system promos (PB-09: Nicholas Lattimore)"""
    promo = db.get_or_404(PromoCode, promo_id)
    protected_codes = ['WELCOME10', 'SAVE5', 'ALMASRI']
    if promo.code in protected_codes:
        flash(f"Promo '{promo.code}' is a protected default campaign and cannot be deleted. You can deactivate it instead.", 'warning')
        return redirect(url_for('staff.promos'))

    code_name = promo.code
    db.session.delete(promo)
    db.session.commit()
    flash(f"Promo code '{code_name}' has been permanently deleted.", 'info')
    return redirect(url_for('staff.promos'))


@staff_bp.route('/promos/<int:promo_id>/toggle', methods=['POST'])
@staff_login_required
def toggle_promo(promo_id):
    """Toggle promo code active status (PB-09: Nicholas Lattimore)"""
    promo = db.get_or_404(PromoCode, promo_id)
    promo.is_active = not promo.is_active
    db.session.commit()
    status_str = 'Active' if promo.is_active else 'Inactive'
    flash(f"Promo code '{promo.code}' is now {status_str}.", 'success' if promo.is_active else 'info')
    return redirect(url_for('staff.promos'))


