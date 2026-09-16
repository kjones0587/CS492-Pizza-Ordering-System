from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import db, Order, Manager

staff_bp = Blueprint('staff', __name__)

def staff_login_required(f):
    """Decorator requiring store manager / staff authentication (PB-07: Michael Fabacher)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
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
            next_url = request.args.get('next')
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
def orders():
    status_filter = request.args.get('status', 'all')
    query = Order.query.order_by(Order.created_at.desc())

    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)

    orders_list = query.all()
    counts = {
        'all': Order.query.count(),
        'Received': Order.query.filter_by(status='Received').count(),
        'Preparing': Order.query.filter_by(status='Preparing').count(),
        'Ready': Order.query.filter_by(status='Ready').count(),
        'Completed': Order.query.filter_by(status='Completed').count(),
    }

    return render_template('staff/orders.html', orders=orders_list, counts=counts, current_filter=status_filter)

@staff_bp.route('/orders/<int:order_id>/status', methods=['POST'])
def update_status(order_id):
    order = db.get_or_404(Order, order_id)
    new_status = request.form.get('status')
    valid_statuses = ['Received', 'Preparing', 'Ready', 'Completed', 'Cancelled']

    if new_status in valid_statuses:
        order.status = new_status
        db.session.commit()
        flash(f'Order {order.order_number} status updated to {new_status}.', 'success')
    else:
        flash('Invalid order status.', 'danger')

    return redirect(url_for('staff.orders', status=request.form.get('current_filter', 'all')))
