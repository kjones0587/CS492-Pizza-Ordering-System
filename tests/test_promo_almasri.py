import pytest
from app.models import db, Category, MenuItem, PromoCode, Order

def test_almasri_promo_seeded_and_active(client, app):
    """Verify that the ALMASRI promo code is seeded in database and active."""
    with app.app_context():
        promo = PromoCode.query.filter_by(code='ALMASRI').first()
        assert promo is not None
        assert promo.discount_type == 'percent'
        assert promo.discount_value == 100.0
        assert promo.is_active is True
        assert 'VIP Faculty Pass' in promo.description

def test_almasri_promo_ajax_api_and_vip_response(client, app):
    """Verify applying ALMASRI promo code via AJAX returns is_vip flag and $0 total."""
    # First add an item to the cart
    with app.app_context():
        item = MenuItem.query.first()
        item_id = item.id

    client.post('/cart/add', data={
        'menu_item_id': item_id,
        'quantity': 2,
        'size_option': 'Large (16")',
        'crust_option': 'Classic Hand-Tossed'
    })

    # Apply ALMASRI in lowercase to verify case-insensitivity
    res = client.post('/cart/apply-promo', data={'promo_code': 'almasri'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['is_vip'] is True
    assert 'Professor always eats free' in data['message']
    assert data['totals']['total_amount'] == 0.0
    assert data['totals']['tax_amount'] == 0.0
    assert data['totals']['delivery_fee'] == 0.0
    assert data['totals']['discount_amount'] == data['totals']['subtotal']
    assert data['totals']['promo_code'] == 'ALMASRI'

def test_almasri_promo_waives_delivery_fee(client, app):
    """Verify that ALMASRI waives the delivery fee ($4.99) on delivery orders."""
    with app.app_context():
        item = MenuItem.query.first()
        item_id = item.id

    client.post('/cart/add', data={'menu_item_id': item_id, 'quantity': 1})

    # Set order_type to delivery
    client.post('/cart/calculate-api', json={'order_type': 'delivery'})

    # Apply promo code ALMASRI
    res = client.post('/cart/apply-promo', data={'promo_code': 'ALMASRI'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    data = res.get_json()
    assert data['totals']['delivery_fee'] == 0.0
    assert data['totals']['tax_amount'] == 0.0
    assert data['totals']['total_amount'] == 0.0

def test_order_submission_with_almasri_clears_session(client, app):
    """Verify submitting an order with ALMASRI records $0 total and clears promo from session."""
    with app.app_context():
        item = MenuItem.query.first()
        item_id = item.id

    client.post('/cart/add', data={'menu_item_id': item_id, 'quantity': 1})
    client.post('/cart/apply-promo', data={'promo_code': 'ALMASRI'})

    # Submit order
    submit_res = client.post('/order/submit', data={
        'customer_name': 'Dr. Almasri',
        'customer_email': 'professor@bellanapolipizza.com',
        'customer_phone': '(555) 123-4567',
        'order_type': 'pickup',
        'special_instructions': 'VIP Capstone Demo Order'
    }, follow_redirects=True)

    assert submit_res.status_code == 200

    # Verify order recorded with $0 total and ALMASRI promo code
    with app.app_context():
        order = Order.query.filter_by(customer_name='Dr. Almasri').first()
        assert order is not None
        assert order.total_amount == 0.0
        assert order.discount_amount == order.subtotal
        assert order.promo_code == 'ALMASRI'

    # Verify session promo code is cleared
    with client.session_transaction() as sess:
        assert 'promo_code' not in sess or sess.get('promo_code') is None
        assert sess.get('cart') == []

def test_clear_cart_purges_promo_code(client, app):
    """Verify that clearing the cart or emptying it completely removes any active promo code."""
    with app.app_context():
        item = MenuItem.query.first()
        item_id = item.id

    # 1. Add item and apply ALMASRI
    client.post('/cart/add', data={'menu_item_id': item_id, 'quantity': 1})
    client.post('/cart/apply-promo', data={'promo_code': 'ALMASRI'})

    # Verify promo code is active
    with client.session_transaction() as sess:
        assert sess.get('promo_code') == 'ALMASRI'

    # 2. Clear cart
    client.post('/cart/clear')

    # Verify promo code is completely purged from session
    with client.session_transaction() as sess:
        assert sess.get('cart') == []
        assert 'promo_code' not in sess or sess.get('promo_code') is None

    # 3. Add a different item to cart
    client.post('/cart/add', data={'menu_item_id': item_id, 'quantity': 1})

    # Verify promo code is NOT automatically applied to the new cart
    res = client.get('/cart/checkout')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    with client.session_transaction() as sess:
        assert sess.get('promo_code') is None

