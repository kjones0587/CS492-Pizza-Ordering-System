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
    assert 'Baking' in data['counts']
    assert 'timestamp' in data

def test_staff_update_order_status_to_baking(client):
    """Verify staff can update status to Baking and it reflects in dashboard."""
    order = Order(
        order_number='ORD-20260922-BAKE1',
        customer_name='Bake Test Customer',
        customer_email='bake@example.com',
        customer_phone='(555) 321-4321',
        order_type='pickup',
        subtotal=18.00,
        tax_amount=1.49,
        delivery_fee=0.0,
        total_amount=19.49,
        status='Preparing',
        created_at=datetime.now(timezone.utc),
        payment_method='cash',
        payment_status='Pending'
    )
    db.session.add(order)
    db.session.commit()

    update_res = client.post(f'/staff/orders/{order.id}/status', data={
        'status': 'Baking'
    }, follow_redirects=True)
    assert update_res.status_code == 200
    html = update_res.data.decode('utf-8')
    assert f'Order {order.order_number} status updated to Baking.' in html
    assert 'Stone Oven' in html

    db_order = db.session.get(Order, order.id)
    assert db_order.status == 'Baking'

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

    # 4. Update status to Baking (Stone Oven) and verify step moves to 3 and timing shows baking in oven
    order.status = 'Baking'
    db.session.commit()
    baking_res = client.get(f'/order/{order.order_number}/track')
    assert baking_res.status_code == 200
    baking_html = baking_res.data.decode('utf-8')
    assert 'stone wood-fired deck oven' in baking_html
    assert 'Baking in Oven' in baking_html
    api_baking_res = client.get(f'/order/api/{order.order_number}/status')
    assert api_baking_res.get_json()['current_step'] == 3

    # 5. Update status to Ready and verify step moves to 4 (Step 3 completed, Step 4 active)
    order.status = 'Ready'
    db.session.commit()
    ready_res = client.get(f'/order/{order.order_number}/track')
    assert ready_res.status_code == 200
    ready_html = ready_res.data.decode('utf-8')
    assert 'Out for Delivery Now!' in ready_html
    api_ready_res = client.get(f'/order/api/{order.order_number}/status')
    assert api_ready_res.get_json()['current_step'] == 4

    # 5. Update status to Completed and verify customer tracker wording updates
    order.status = 'Completed'
    db.session.commit()
    complete_res = client.get(f'/order/{order.order_number}/track')
    assert complete_res.status_code == 200
    complete_html = complete_res.data.decode('utf-8')
    assert '4. Delivered & Enjoyed!' in complete_html
    assert 'Order Complete' in complete_html
    assert 'Fulfilled & Enjoyed' in complete_html

    # 5. Verify staff navigation is suppressed on tracker page even if manager session is active
    with client.session_transaction() as sess:
        sess['staff_user_id'] = 1
        sess['staff_username'] = 'manager'
    suppressed_res = client.get(f'/order/{order.order_number}/track')
    assert 'Staff Orders' not in suppressed_res.data.decode('utf-8')

    # 6. Invalid order returns 404
    invalid_res = client.get('/order/ORD-NONEXISTENT/track')
    assert invalid_res.status_code == 404

def test_customer_tracker_session_retention_and_lookup(client):
    """Verify customer can navigate away and easily return to live tracker via session & lookup."""
    order = Order(
        order_number='ORD-20260922-RETN1',
        customer_name='Return Customer',
        customer_email='return@example.com',
        customer_phone='(555) 777-8888',
        order_type='pickup',
        subtotal=15.00,
        tax_amount=1.24,
        delivery_fee=0.0,
        total_amount=16.24,
        status='Preparing',
        created_at=datetime.now(timezone.utc),
        payment_method='cash',
        payment_status='Pending'
    )
    db.session.add(order)
    db.session.commit()

    # 1. Visit tracker directly -> sets active_order_number in session
    track_res = client.get(f'/order/{order.order_number}/track')
    assert track_res.status_code == 200

    # 2. Navigate away to the menu page -> verify Track Order link is in navbar
    menu_res = client.get('/menu/')
    assert menu_res.status_code == 200
    menu_html = menu_res.data.decode('utf-8')
    assert 'Track Order' in menu_html
    assert f'/order/{order.order_number}/track' in menu_html

    # 3. Navigate to generic /order/track -> auto-redirects directly to active order tracker
    redir_res = client.get('/order/track')
    assert redir_res.status_code == 302
    assert redir_res.headers['Location'] == f'/order/{order.order_number}/track'

    # 4. Visit lookup page explicitly with ?new=1
    lookup_res = client.get('/order/track?new=1')
    assert lookup_res.status_code == 200
    assert 'Track Your Order' in lookup_res.data.decode('utf-8')

    # 5. POST to lookup page with valid order number
    post_res = client.post('/order/track', data={
        'search_query': f'#{order.order_number}'
    })
    assert post_res.status_code == 302
    assert post_res.headers['Location'] == f'/order/{order.order_number}/track'

    # 6. POST to lookup with customer name (case-insensitive)
    name_post = client.post('/order/track', data={
        'search_query': 'return customer'
    })
    assert name_post.status_code == 302
    assert name_post.headers['Location'] == f'/order/{order.order_number}/track'

    # 7. POST to lookup with customer phone number
    phone_post = client.post('/order/track', data={
        'search_query': '5557778888'
    })
    assert phone_post.status_code == 302
    assert phone_post.headers['Location'] == f'/order/{order.order_number}/track'

    # 8. POST to lookup with customer email (case-insensitive)
    email_post = client.post('/order/track', data={
        'search_query': 'RETURN@EXAMPLE.COM'
    })
    assert email_post.status_code == 302
    assert email_post.headers['Location'] == f'/order/{order.order_number}/track'

    # 9. POST to lookup with invalid search query
    bad_post = client.post('/order/track', data={
        'search_query': 'NONEXISTENT_USER_XYZ'
    }, follow_redirects=True)
    assert bad_post.status_code == 200
    assert 'No orders found' in bad_post.data.decode('utf-8')

def test_dynamic_stepper_variability_by_order_items(client):
    """Verify stepper dynamically adapts steps based on whether order has pizza, prepared food, or drinks only."""
    # 1. Non-pizza prepared food order (Salad + Drink, as in user screenshot)
    salad_order = Order(
        order_number='ORD-20260922-SALAD',
        customer_name='Salad Fan',
        customer_email='salad@example.com',
        customer_phone='(555) 234-5678',
        order_type='pickup',
        subtotal=12.98,
        tax_amount=1.07,
        delivery_fee=0.0,
        total_amount=14.05,
        status='Received',
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(salad_order)
    db.session.flush()

    item1 = OrderItem(order_id=salad_order.id, item_name='Classic Caesar Salad', unit_price=8.99, quantity=1, line_total=8.99)
    item2 = OrderItem(order_id=salad_order.id, item_name='Blood Orange Italian Aranciata', unit_price=3.99, quantity=1, line_total=3.99)
    db.session.add_all([item1, item2])
    db.session.commit()

    # Track salad order: verify 3 steps (Kitchen Prep), Stone Oven step omitted!
    salad_res = client.get(f'/order/{salad_order.order_number}/track')
    assert salad_res.status_code == 200
    salad_html = salad_res.data.decode('utf-8')
    assert '1. Received' in salad_html
    assert '2. Kitchen Prep' in salad_html
    assert '3. Ready for Pickup' in salad_html
    assert 'Stone Oven' not in salad_html
    assert '10 - 15 mins (Kitchen Prep)' in salad_html

    # Check API returns kitchen_prep and 3 total steps
    salad_api = client.get(f'/order/api/{salad_order.order_number}/status').get_json()
    assert salad_api['order_category'] == 'kitchen_prep'
    assert salad_api['total_steps'] == 3

    # 2. Beverage-only order (e.g. 1x Soda)
    drink_order = Order(
        order_number='ORD-20260922-DRINK',
        customer_name='Drink Fan',
        customer_email='drink@example.com',
        customer_phone='(555) 345-6789',
        order_type='pickup',
        subtotal=3.99,
        tax_amount=0.33,
        delivery_fee=0.0,
        total_amount=4.32,
        status='Received',
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(drink_order)
    db.session.flush()

    drink_item = OrderItem(order_id=drink_order.id, item_name='Blood Orange Italian Aranciata', unit_price=3.99, quantity=1, line_total=3.99)
    db.session.add(drink_item)
    db.session.commit()

    # Track drink order: verify 2 steps (Received -> Ready), no preparing, no stone oven
    drink_res = client.get(f'/order/{drink_order.order_number}/track')
    assert drink_res.status_code == 200
    drink_html = drink_res.data.decode('utf-8')
    assert '1. Received' in drink_html
    assert '2. Ready for Pickup' in drink_html
    assert 'Stone Oven' not in drink_html
    assert 'Preparing' not in drink_html
    assert '3 - 5 mins (Express Pickup)' in drink_html

    # Check API returns beverage_only and 2 total steps
    drink_api = client.get(f'/order/api/{drink_order.order_number}/status').get_json()
    assert drink_api['order_category'] == 'beverage_only'
    assert drink_api['total_steps'] == 2

    # 3. Combo order (Pizza + Salad + Drink): Stone oven included, 4 steps, step 2 description updated
    combo_order = Order(
        order_number='ORD-20260922-COMBO',
        customer_name='Combo Lover',
        customer_email='combo@example.com',
        customer_phone='(555) 456-7890',
        order_type='pickup',
        subtotal=34.98,
        tax_amount=2.89,
        delivery_fee=0.0,
        total_amount=37.87,
        status='Received',
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(combo_order)
    db.session.flush()

    combo_pizza = OrderItem(
        order_id=combo_order.id,
        item_name='Margherita D.O.P.',
        size_option='Large (14")',
        crust_option='Stone Deck Hand-Tossed',
        unit_price=21.99,
        quantity=1,
        line_total=21.99
    )
    combo_salad = OrderItem(order_id=combo_order.id, item_name='Classic Caesar Salad', unit_price=8.99, quantity=1, line_total=8.99)
    combo_drink = OrderItem(order_id=combo_order.id, item_name='Blood Orange Italian Aranciata', unit_price=3.99, quantity=1, line_total=3.99)
    db.session.add_all([combo_pizza, combo_salad, combo_drink])
    db.session.commit()

    combo_res = client.get(f'/order/{combo_order.order_number}/track')
    assert combo_res.status_code == 200
    combo_html = combo_res.data.decode('utf-8')
    assert '1. Received' in combo_html
    assert '2. Preparing' in combo_html
    assert '3. Stone Oven' in combo_html
    assert '4. Ready for Pickup' in combo_html
    assert 'Prepping artisan dough, salads &amp; sides' in combo_html or 'Prepping artisan dough, salads & sides' in combo_html

    combo_api = client.get(f'/order/api/{combo_order.order_number}/status').get_json()
    assert combo_api['order_category'] == 'pizza'
    assert combo_api['total_steps'] == 4

