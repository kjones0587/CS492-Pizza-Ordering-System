import pytest
from datetime import datetime, timezone
from app.models import db, Order, OrderItem, MenuItem, Category, PromoCode

def test_staff_promos_dashboard_and_creation(client):
    """PB-08 / PB-09 (Nicholas Lattimore): Verify staff promo management dashboard & code creation."""
    # 1. View staff promo codes portal
    res = client.get('/staff/promos')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'Promo Code Management' in html
    assert 'Create Promo Code' in html

    # 2. Create a new promo code
    create_res = client.post('/staff/promos/create', data={
        'code': 'TUESDAY25',
        'discount_type': 'percent',
        'discount_value': '25.0',
        'min_subtotal': '15.00',
        'description': 'Tuesday 25% Off Super Special'
    }, follow_redirects=True)
    assert create_res.status_code == 200
    assert 'Successfully created active promo code' in create_res.data.decode('utf-8')
    assert 'TUESDAY25' in create_res.data.decode('utf-8')

    # Verify promo exists in database
    promo = PromoCode.query.filter_by(code='TUESDAY25').first()
    assert promo is not None
    assert promo.discount_value == 25.0
    assert promo.discount_type == 'percent'
    assert promo.min_subtotal == 15.00
    assert promo.is_active is True

    # 3. Duplicate code creation should fail with alert
    dup_res = client.post('/staff/promos/create', data={
        'code': 'TUESDAY25',
        'discount_type': 'fixed',
        'discount_value': '5.0',
        'min_subtotal': '0.00',
        'description': 'Duplicate attempt'
    }, follow_redirects=True)
    assert dup_res.status_code == 200
    assert 'already exists' in dup_res.data.decode('utf-8')

def test_staff_promos_toggle_status(client):
    """PB-08 / PB-09 (Nicholas Lattimore): Verify 1-click promo code enable/disable toggle."""
    promo = PromoCode.query.first()
    assert promo is not None
    initial_status = promo.is_active

    # Toggle off
    toggle_res = client.post(f'/staff/promos/{promo.id}/toggle', follow_redirects=True)
    assert toggle_res.status_code == 200
    updated_promo = db.session.get(PromoCode, promo.id)
    assert updated_promo.is_active == (not initial_status)

    # Toggle back
    client.post(f'/staff/promos/{promo.id}/toggle', follow_redirects=True)
    restored_promo = db.session.get(PromoCode, promo.id)
    assert restored_promo.is_active == initial_status

def test_staff_menu_update_price(client):
    """PB-08 (Nicholas Lattimore): Verify staff 1-click base price editor and input validation."""
    item = MenuItem.query.filter_by(name='Margherita Classico').first()
    assert item is not None

    # 1. Negative or zero price should be rejected
    fail_res = client.post(f'/staff/menu/{item.id}/update-price', data={
        'base_price': '-5.00'
    }, follow_redirects=True)
    assert fail_res.status_code == 200
    assert 'Please enter a valid positive base price' in fail_res.data.decode('utf-8')

    # 2. Valid new price
    valid_res = client.post(f'/staff/menu/{item.id}/update-price', data={
        'base_price': '15.99'
    }, follow_redirects=True)
    assert valid_res.status_code == 200
    assert 'Updated base price for' in valid_res.data.decode('utf-8')
    assert '15.99' in valid_res.data.decode('utf-8')

    updated_item = db.session.get(MenuItem, item.id)
    assert updated_item.base_price == 15.99

def test_staff_live_polling_endpoint(client):
    """PB-05 / PB-07 (Michael Fabacher): Verify kitchen live order polling API endpoint."""
    res = client.get('/staff/api/orders/poll')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'latest_order_id' in data
    assert 'counts' in data
    assert 'Received' in data['counts']
    assert 'timestamp' in data

def test_staff_update_order_notes(client):
    """PB-07 (Michael Fabacher): Verify internal kitchen staff prep notes update."""
    order = Order(
        order_number='ORD-20260922-TEST1',
        customer_name='John Doe',
        customer_email='johndoe@example.com',
        customer_phone='(555) 123-4567',
        order_type='pickup',
        subtotal=20.00,
        tax_amount=1.65,
        delivery_fee=0.0,
        total_amount=21.65,
        status='Received',
        created_at=datetime.now(timezone.utc),
        payment_method='cash',
        payment_status='Pending'
    )
    db.session.add(order)
    db.session.commit()

    notes_res = client.post(f'/staff/orders/{order.id}/notes', data={
        'staff_notes': 'Gluten allergy prep station 1, extra crispy deck oven finish'
    }, follow_redirects=True)
    assert notes_res.status_code == 200
    assert 'Internal kitchen note updated' in notes_res.data.decode('utf-8')

    updated_order = db.session.get(Order, order.id)
    assert updated_order.staff_notes == 'Gluten allergy prep station 1, extra crispy deck oven finish'

def test_customer_live_order_tracker(client):
    """PB-05 / PB-10 (Ayden Lotter): Verify customer live visual order tracker and status API."""
    order = Order(
        order_number='ORD-20260922-TRK1',
        customer_name='Sarah Connor',
        customer_email='sarah@example.com',
        customer_phone='(555) 987-6543',
        order_type='delivery',
        delivery_address='742 Evergreen Terrace',
        subtotal=28.50,
        tax_amount=2.35,
        delivery_fee=3.99,
        total_amount=34.84,
        status='Received',
        created_at=datetime.now(timezone.utc),
        payment_method='credit_card',
        payment_status='Paid',
        card_brand='Visa',
        card_last4='4242'
    )
    db.session.add(order)
    db.session.flush()

    item = OrderItem(
        order_id=order.id,
        item_name='Pepperoni Rustica',
        size_option='Large (14")',
        crust_option='Stone Deck Hand-Tossed',
        unit_price=22.00,
        quantity=1,
        line_total=22.00
    )
    db.session.add(item)
    db.session.commit()

    # 1. Tracker web page loads with 4-step progress stepper
    track_res = client.get(f'/order/{order.order_number}/track')
    assert track_res.status_code == 200
    track_html = track_res.data.decode('utf-8')
    assert 'LIVE ORDER TRACKER' in track_html
    assert 'Sarah Connor' in track_html
    assert '742 Evergreen Terrace' in track_html
    assert 'Pepperoni Rustica' in track_html
    assert '1. Received' in track_html
    assert '2. Preparing' in track_html
    assert '3. Stone Oven' in track_html
    assert '4. Out for Delivery' in track_html

    # 2. Live tracker API endpoint
    api_res = client.get(f'/order/api/{order.order_number}/status')
    assert api_res.status_code == 200
    api_data = api_res.get_json()
    assert api_data['success'] is True
    assert api_data['order_number'] == order.order_number
    assert api_data['status'] == 'Received'
    assert api_data['current_step'] == 1

    # 3. Update status to Preparing and verify API step moves to 2
    order.status = 'Preparing'
    db.session.commit()
    api_prep_res = client.get(f'/order/api/{order.order_number}/status')
    assert api_prep_res.get_json()['current_step'] == 2

    # 4. Invalid order returns 404
    invalid_res = client.get('/order/ORD-NONEXISTENT/track')
    assert invalid_res.status_code == 404
