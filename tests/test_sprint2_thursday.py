import pytest
from datetime import datetime, timezone
from app.models import db, Order, OrderItem, MenuItem, Category, PromoCode

def test_promo_edit_delete_and_usage_count(client):
    """Verify managers can edit promos, view usage count badges, and protected promos cannot be deleted (PB-09: Nicholas Lattimore)."""
    # 1. Authenticate as manager
    with client.session_transaction() as sess:
        sess['staff_user_id'] = 1
        sess['staff_username'] = 'manager'
        sess['staff_role'] = 'Store Manager'

    # Ensure a protected promo exists
    welcome_promo = PromoCode.query.filter_by(code='WELCOME10').first()
    if not welcome_promo:
        welcome_promo = PromoCode(
            code='WELCOME10',
            description='Default Welcome Discount',
            discount_type='percent',
            discount_value=10.0,
            min_subtotal=15.0,
            is_active=True
        )
        db.session.add(welcome_promo)
        db.session.commit()

    # 2. Create custom promo code
    create_res = client.post('/staff/promos/create', data={
        'code': 'THURSDAY20',
        'description': 'Thursday Flash Special',
        'discount_type': 'percent',
        'discount_value': '20.0',
        'min_subtotal': '25.0'
    }, follow_redirects=True)
    assert create_res.status_code == 200
    thursday_promo = PromoCode.query.filter_by(code='THURSDAY20').first()
    assert thursday_promo is not None
    assert thursday_promo.discount_value == 20.0

    # 3. View /staff/promos and check redemption count badge rendering
    promos_page = client.get('/staff/promos')
    assert promos_page.status_code == 200
    html = promos_page.data.decode('utf-8')
    assert 'THURSDAY20' in html
    assert '0 used' in html

    # 4. Edit promo code rules
    edit_res = client.post(f'/staff/promos/{thursday_promo.id}/edit', data={
        'description': 'Updated Thursday Super Special 25%',
        'discount_type': 'percent',
        'discount_value': '25.0',
        'min_subtotal': '30.0'
    }, follow_redirects=True)
    assert edit_res.status_code == 200
    db.session.refresh(thursday_promo)
    assert thursday_promo.discount_value == 25.0
    assert thursday_promo.min_subtotal == 30.0
    assert 'Updated Thursday' in thursday_promo.description

    # 5. Protected promo deletion prevention
    del_protected_res = client.post(f'/staff/promos/{welcome_promo.id}/delete', follow_redirects=True)
    assert del_protected_res.status_code == 200
    protected_html = del_protected_res.data.decode('utf-8')
    assert 'protected default campaign' in protected_html
    # Verify WELCOME10 still exists
    assert PromoCode.query.filter_by(code='WELCOME10').first() is not None

    # 6. Delete custom promo code
    del_custom_res = client.post(f'/staff/promos/{thursday_promo.id}/delete', follow_redirects=True)
    assert del_custom_res.status_code == 200
    custom_html = del_custom_res.data.decode('utf-8')
    assert 'permanently deleted' in custom_html
    assert PromoCode.query.filter_by(code='THURSDAY20').first() is None


def test_kitchen_ticket_and_rush_delay(client):
    """Verify kitchen staff can view prep ticket slips and annotate rush delays (PB-07: Michael Fabacher)."""
    with client.session_transaction() as sess:
        sess['staff_user_id'] = 1
        sess['staff_username'] = 'chef_michael'
        sess['staff_role'] = 'Kitchen Staff'

    # Create category and menu items
    cat = Category.query.filter_by(slug='pizzas').first()
    if not cat:
        cat = Category(name='Pizzas', slug='pizzas', display_order=1)
        db.session.add(cat)
        db.session.commit()

    item = MenuItem(
        category_id=cat.id,
        name='Thursday Fire Brick Margherita',
        base_price=16.00,
        description='Wood-fired pizza',
        is_available=True
    )
    db.session.add(item)
    db.session.commit()

    # Create order with items
    order = Order(
        order_number='ORD-20260923-RUSH01',
        customer_name='Marcus Antonius',
        customer_email='marcus@example.com',
        customer_phone='(555) 777-3322',
        order_type='pickup',
        subtotal=16.00,
        tax_amount=1.32,
        delivery_fee=0.0,
        total_amount=17.32,
        status='Preparing',
        created_at=datetime.now(timezone.utc),
        payment_method='cash',
        payment_status='Pending'
    )
    db.session.add(order)
    db.session.commit()

    order_item = OrderItem(
        order_id=order.id,
        menu_item_id=item.id,
        item_name=item.name,
        size_option='Large (14")',
        crust_option='Thin Crust',
        toppings='Fresh Basil, Garlic, Buffalo Mozzarella',
        unit_price=16.00,
        quantity=1,
        line_total=16.00
    )
    db.session.add(order_item)
    db.session.commit()

    # 1. View orders board and verify kitchen ticket modal
    orders_page = client.get('/staff/orders')
    assert orders_page.status_code == 200
    html = orders_page.data.decode('utf-8')
    assert f'ticketModal{order.id}' in html
    assert 'KITCHEN STATION PREP TICKET' in html
    assert 'Thursday Fire Brick Margherita' in html
    assert 'Buffalo Mozzarella' in html

    # 2. Add Rush Delay note
    rush_res = client.post(f'/staff/orders/{order.id}/rush-delay', data={
        'delay_minutes': '15',
        'current_filter': 'all'
    }, follow_redirects=True)
    assert rush_res.status_code == 200
    db.session.refresh(order)
    assert '[RUSH: +15 min delay]' in order.staff_notes
    assert 'Added +15 min rush delay' in rush_res.data.decode('utf-8')


def test_customer_order_reorder_flow(client):
    """Verify 1-click reorder loads past order items into cart and displays Order Again on completed tracker (PB-10: Ayden Lotter)."""
    # Create category and menu item
    cat = Category.query.first()
    if not cat:
        cat = Category(name='Specialty', slug='specialty', display_order=1)
        db.session.add(cat)
        db.session.commit()

    item = MenuItem.query.first()
    if not item:
        item = MenuItem(
            category_id=cat.id,
            name='Bella Supreme',
            base_price=19.99,
            description='Loaded supreme',
            is_available=True
        )
        db.session.add(item)
        db.session.commit()

    # Create completed order
    order = Order(
        order_number='ORD-20260923-REORD1',
        customer_name='Ayden Customer',
        customer_email='ayden@example.com',
        customer_phone='(555) 444-2211',
        order_type='delivery',
        delivery_address='456 Hilltop Ave',
        subtotal=19.99,
        tax_amount=1.65,
        delivery_fee=3.99,
        total_amount=25.63,
        status='Completed',
        created_at=datetime.now(timezone.utc),
        payment_method='credit_card',
        payment_status='Paid'
    )
    db.session.add(order)
    db.session.commit()

    order_item = OrderItem(
        order_id=order.id,
        menu_item_id=item.id,
        item_name=item.name,
        size_option='Medium (12")',
        crust_option='Hand Tossed',
        toppings='Pepperoni, Italian Sausage',
        unit_price=19.99,
        quantity=1,
        line_total=19.99
    )
    db.session.add(order_item)
    db.session.commit()

    # 1. Check Completed Live Tracker shows "Order Again" button
    track_page = client.get(f'/order/{order.order_number}/track')
    assert track_page.status_code == 200
    track_html = track_page.data.decode('utf-8')
    assert 'Order Again' in track_html
    assert f'/order/{order.order_number}/reorder' in track_html

    # 2. Trigger 1-Click Reorder route
    reorder_res = client.get(f'/order/{order.order_number}/reorder', follow_redirects=True)
    assert reorder_res.status_code == 200
    reorder_html = reorder_res.data.decode('utf-8')
    assert f'Loaded all items from Order #{order.order_number}' in reorder_html

    # 3. Check items are present in cart session
    with client.session_transaction() as sess:
        cart = sess.get('cart', [])
        assert len(cart) == 1
        assert cart[0]['name'] == item.name
        assert cart[0]['size_option'] == 'Medium (12")'
        assert cart[0]['crust_option'] == 'Hand Tossed'
        assert 'Pepperoni' in cart[0]['toppings']
