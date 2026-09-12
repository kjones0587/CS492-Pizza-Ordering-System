import pytest
from app.models import MenuItem, Order, OrderItem

def test_pb01_restaurant_info_and_home_page(client):
    """PB-01: Home page includes business description, photos, hours, location, and contact information."""
    res = client.get('/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Restaurant name and branding
    assert 'Bella Napoli' in html
    # Description / heritage
    assert 'Wood-Fired' in html or 'Neapolitan' in html
    # Operating Hours
    assert 'Monday - Thursday' in html
    assert '11:00 AM - 10:00 PM' in html
    # Location & Contact
    assert 'Evergreen Terrace' in html
    assert '(555) 392-4920' in html
    assert 'orders@bellanapolipizza.com' in html
    # Navigation elements
    assert 'Browse Menu' in html
    assert 'Staff Portal' in html
    assert 'Cart' in html

def test_pb02_menu_browsing_and_item_details(client):
    """PB-02: Menu is grouped by category. Shows item name, description, price, available options, and marks unavailable items."""
    res = client.get('/menu/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Categories
    assert 'Specialty Pizzas' in html
    assert 'Appetizers' in html
    assert 'Beverages' in html
    assert 'Desserts' in html

    # Items and prices
    assert 'Margherita Classico' in html
    assert '14.99' in html
    assert 'Pepperoni Rustica' in html

    # Acceptance criteria: Unavailable items are clearly marked
    assert 'Sold Out' in html or 'Currently Unavailable' in html
    assert 'Diavola Piccante' in html

    # JSON endpoint for item details / customization
    item = MenuItem.query.filter_by(name='Margherita Classico').first()
    assert item is not None
    res_item = client.get(f'/menu/item/{item.id}')
    assert res_item.status_code == 200
    data = res_item.get_json()
    assert data['name'] == 'Margherita Classico'
    assert 'sizes' in data['options']
    assert 'crusts' in data['options']

def test_pb03_order_builder_and_shopping_cart(client):
    """PB-03: Add items to cart, change quantities, remove items, review cart, handle empty-cart behavior."""
    # 1. Empty cart behavior
    res = client.get('/cart/')
    assert res.status_code == 200
    assert 'Your Cart is Currently Empty' in res.data.decode('utf-8')
    assert 'Browse Our Menu' in res.data.decode('utf-8')

    # 2. Add item to cart
    item = MenuItem.query.filter_by(is_available=True).first()
    add_res = client.post('/cart/add', data={
        'menu_item_id': item.id,
        'size_option': 'Medium (12")',
        'crust_option': 'Classic Hand-Tossed',
        'special_notes': 'Extra crispy',
        'quantity': 2
    }, follow_redirects=True)
    assert add_res.status_code == 200
    cart_html = add_res.data.decode('utf-8')
    assert item.name in cart_html
    assert 'Medium' in cart_html
    assert 'Extra crispy' in cart_html

    # 3. Increase quantity
    upd_res = client.post('/cart/update', data={'index': 0, 'action': 'increase'}, follow_redirects=True)
    assert upd_res.status_code == 200

    # 4. Decrease quantity
    down_res = client.post('/cart/update', data={'index': 0, 'action': 'decrease'}, follow_redirects=True)
    assert down_res.status_code == 200

    # 5. Remove item
    rem_res = client.post('/cart/remove/0', follow_redirects=True)
    assert rem_res.status_code == 200
    assert 'Your Cart is Currently Empty' in rem_res.data.decode('utf-8')

def test_pb04_final_bill_calculation_and_order_review(client):
    """PB-04: System displays selected items, quantities, subtotal, taxes or fees, and final total. Customer cannot submit empty order."""
    # Cannot checkout with empty cart
    checkout_res = client.get('/cart/checkout', follow_redirects=True)
    assert 'Your cart is empty' in checkout_res.data.decode('utf-8')

    # Cannot submit empty order
    empty_submit = client.post('/order/submit', data={'customer_name': 'Test User'}, follow_redirects=True)
    assert 'Cannot submit an empty order' in empty_submit.data.decode('utf-8')

    # Add item to cart
    item = MenuItem.query.filter_by(is_available=True).first()
    client.post('/cart/add', data={
        'menu_item_id': item.id,
        'quantity': 1
    })

    # Test checkout view
    res = client.get('/cart/checkout')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'Subtotal' in html
    assert 'Estimated Tax (8.25%)' in html
    assert 'Final Total' in html

    # Test dynamic bill calculation API
    api_res = client.post('/cart/calculate-api', json={'order_type': 'delivery'})
    assert api_res.status_code == 200
    calc_data = api_res.get_json()
    assert calc_data['success'] is True
    assert calc_data['totals']['delivery_fee'] == 4.99
    expected_tax = round(calc_data['totals']['subtotal'] * 0.0825, 2)
    assert calc_data['totals']['tax_amount'] == expected_tax
    assert calc_data['totals']['total_amount'] == round(calc_data['totals']['subtotal'] + expected_tax + 4.99, 2)

def test_pb05_customer_order_submission_and_confirmation(client):
    """PB-05: Required info validated, order record created, confirmation screen shown with order number, and visible on staff dashboard."""
    # Add item to cart first
    item = MenuItem.query.filter_by(is_available=True).first()
    client.post('/cart/add', data={
        'menu_item_id': item.id,
        'size_option': 'Large (16")',
        'crust_option': 'Classic Hand-Tossed',
        'quantity': 1
    })

    # Test validation error (missing required fields)
    fail_submit = client.post('/order/submit', data={
        'customer_name': '',
        'customer_email': 'invalid-email',
        'customer_phone': '',
        'order_type': 'delivery',
        'delivery_address': ''
    }, follow_redirects=True)
    assert 'Customer Name is required.' in fail_submit.data.decode('utf-8')
    assert 'A valid Email address is required.' in fail_submit.data.decode('utf-8')
    assert 'Phone Number is required.' in fail_submit.data.decode('utf-8')
    assert 'Delivery Address is required for delivery orders.' in fail_submit.data.decode('utf-8')

    # Successful submission (Pickup)
    valid_submit = client.post('/order/submit', data={
        'customer_name': 'Kellen Jones',
        'customer_email': 'kjones@example.com',
        'customer_phone': '(555) 987-6543',
        'order_type': 'pickup',
        'special_instructions': 'Extra parmesan packets please'
    }, follow_redirects=True)

    assert valid_submit.status_code == 200
    confirm_html = valid_submit.data.decode('utf-8')
    assert 'Order Received!' in confirm_html
    assert 'ORD-' in confirm_html
    assert 'Kellen Jones' in confirm_html
    assert 'Extra parmesan packets please' in confirm_html

    # Verify order in database
    saved_order = Order.query.filter_by(customer_name='Kellen Jones').first()
    assert saved_order is not None
    assert saved_order.order_number.startswith('ORD-')
    assert len(saved_order.items) == 1
    assert saved_order.items[0].size_option == 'Large (16")'

    # Verify visible on Restaurant Staff Dashboard (PB-05 acceptance criteria)
    staff_res = client.get('/staff/orders')
    assert staff_res.status_code == 200
    staff_html = staff_res.data.decode('utf-8')
    assert saved_order.order_number in staff_html
    assert 'Kellen Jones' in staff_html
    assert '(555) 987-6543' in staff_html

    # Test staff updating order status
    status_update = client.post(f'/staff/orders/{saved_order.id}/status', data={
        'status': 'Preparing',
        'current_filter': 'all'
    }, follow_redirects=True)
    assert status_update.status_code == 200
    assert saved_order.status == 'Preparing'

def test_t1_06_responsive_layout_review(client):
    """T1-06 (PB-10): Review Sprint 1 pages for responsive layout (mobile, tablet, desktop)."""
    endpoints = ['/', '/menu/', '/cart/', '/staff/orders']
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        # Viewport meta tag for mobile scaling
        assert 'name="viewport"' in html
        assert 'width=device-width' in html
        # Responsive navbar toggle for mobile screens
        assert 'navbar-toggler' in html
        # Responsive Bootstrap grid system
        assert 'container' in html
        assert 'col-' in html or 'col-md-' in html or 'col-lg-' in html

# =============================================================================
# Task T1-03: Cart Boundary & Edge-Case Test Suite
# Author / Owner: Kellen Jones (Scrum Master & Development Team)
# Scope: Validates duplicate item merging, customization isolation, defensive
# quantity boundary limits [1, 50], notes sanitization, and AJAX response schemas.
# =============================================================================

def test_t1_03_cart_duplicate_item_merging(client):
    """T1-03: Adding identical item configuration merges quantity instead of duplicating lines."""
    item = MenuItem.query.filter_by(name='Margherita Classico').first()
    assert item is not None

    # First add: 2x Personal Margherita
    client.post('/cart/add', data={
        'menu_item_id': item.id,
        'size_option': 'Personal (10")',
        'crust_option': 'Classic Hand-Tossed',
        'special_notes': 'Extra basil',
        'quantity': 2
    })

    # Second add: 3x identical configuration
    res = client.post('/cart/add', data={
        'menu_item_id': item.id,
        'size_option': 'Personal (10")',
        'crust_option': 'Classic Hand-Tossed',
        'special_notes': 'Extra basil',
        'quantity': 3
    }, follow_redirects=True)

    cart_html = res.data.decode('utf-8')
    # Should show merged quantity 5
    assert '5' in cart_html
    # Subtotal should equal 5 * base_price
    expected_subtotal = round(5 * item.base_price, 2)
    assert f"${expected_subtotal:.2f}" in cart_html

def test_t1_03_cart_distinct_customizations_separation(client):
    """T1-03: Different sizes or crusts for same pizza are kept as distinct line items."""
    item = MenuItem.query.filter_by(name='Pepperoni Rustica').first()
    assert item is not None

    # Add 1: Personal size
    client.post('/cart/add', data={
        'menu_item_id': item.id,
        'size_option': 'Personal (10")',
        'crust_option': 'Classic Hand-Tossed',
        'quantity': 1
    })

    # Add 2: Large size (+6.50) with Stuffed Crust (+3.00)
    res = client.post('/cart/add', data={
        'menu_item_id': item.id,
        'size_option': 'Large (16")',
        'crust_option': 'Garlic Herb Stuffed Crust',
        'quantity': 1
    }, follow_redirects=True)

    cart_html = res.data.decode('utf-8')
    # Both distinct options must appear in cart
    assert 'Personal' in cart_html
    assert 'Large' in cart_html
    assert 'Garlic Herb Stuffed Crust' in cart_html

def test_t1_03_cart_quantity_clamping_and_boundaries(client):
    """T1-03: Defensive server-side boundaries clamp quantities between 1 and 50."""
    item = MenuItem.query.filter_by(name='Margherita Classico').first()
    assert item is not None

    # Test 1: Submitting an extreme quantity (e.g. 999) is clamped to MAX_ITEM_QUANTITY (50)
    res_add = client.post('/cart/add', data={
        'menu_item_id': item.id,
        'quantity': 999
    }, follow_redirects=True)
    assert '50' in res_add.data.decode('utf-8')

    # Test 2: Submitting 0 or negative quantity clamps to 1
    client.post('/cart/clear')
    res_zero = client.post('/cart/add', data={
        'menu_item_id': item.id,
        'quantity': -5
    }, follow_redirects=True)
    assert '1' in res_zero.data.decode('utf-8')

    # Test 3: Updating quantity to 0 removes the line item
    res_remove = client.post('/cart/update', data={
        'index': 0,
        'action': 'set',
        'quantity': 0
    }, follow_redirects=True)
    assert 'Your Cart is Currently Empty' in res_remove.data.decode('utf-8')

def test_t1_03_cart_special_notes_sanitization(client):
    """T1-03: Special notes exceeding 200 characters are safely bounded to prevent cookie bloat."""
    item = MenuItem.query.filter_by(name='Margherita Classico').first()
    assert item is not None

    oversized_notes = 'A' * 300  # 300 characters
    res = client.post('/cart/add', data={
        'menu_item_id': item.id,
        'special_notes': oversized_notes,
        'quantity': 1
    }, follow_redirects=True)

    cart_html = res.data.decode('utf-8')
    # 200 'A' characters should be present, but not 300
    assert 'A' * 200 in cart_html
    assert 'A' * 250 not in cart_html

def test_t1_03_cart_sold_out_rejection(client):
    """T1-03: Adding an unavailable item returns 400 for AJAX or redirects with danger flash."""
    sold_out_item = MenuItem.query.filter_by(is_available=False).first()
    assert sold_out_item is not None

    # Form POST rejection
    res = client.post('/cart/add', data={'menu_item_id': sold_out_item.id}, follow_redirects=True)
    assert 'currently out of stock' in res.data.decode('utf-8')

    # AJAX POST rejection
    ajax_res = client.post('/cart/add', data={'menu_item_id': sold_out_item.id}, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert ajax_res.status_code == 400
    json_data = ajax_res.get_json()
    assert json_data['success'] is False
    assert 'sold out' in json_data['message'].lower()

def test_t1_03_cart_ajax_operations(client):
    """T1-03: AJAX cart add, update, and remove endpoints return well-formed JSON payloads."""
    item = MenuItem.query.filter_by(is_available=True).first()
    assert item is not None

    # AJAX Add
    res_add = client.post('/cart/add', data={
        'menu_item_id': item.id,
        'quantity': 2
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res_add.status_code == 200
    data_add = res_add.get_json()
    assert data_add['success'] is True
    assert data_add['cart_count'] == 2
    assert data_add['item_name'] == item.name
    assert data_add['quantity'] == 2
    assert data_add['unit_price'] == item.base_price
    assert data_add['cart_subtotal'] == round(item.base_price * 2, 2)

    # AJAX Update Quantity
    res_upd = client.post('/cart/update', data={
        'index': 0,
        'action': 'increase'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res_upd.status_code == 200
    data_upd = res_upd.get_json()
    assert data_upd['success'] is True
    assert data_upd['totals']['item_count'] == 3

    # AJAX Remove Item
    res_rem = client.post('/cart/remove/0', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res_rem.status_code == 200
    data_rem = res_rem.get_json()
    assert data_rem['success'] is True
    assert data_rem['totals']['item_count'] == 0


def test_t1_03_cart_toast_and_modal_ajax_payload(client):
    """T1-03: Modal AJAX add-to-cart returns comprehensive metadata for toast notifications and badge animations."""
    pizza = MenuItem.query.filter(MenuItem.category.has(slug='specialty-pizzas'), MenuItem.is_available == True).first()
    assert pizza is not None

    res = client.post('/cart/add', data={
        'menu_item_id': pizza.id,
        'size_option': 'Large (16")',
        'crust_option': 'Gluten-Free Cauliflower Crust',
        'special_notes': 'Extra crispy crust',
        'quantity': 3
    }, headers={'X-Requested-With': 'XMLHttpRequest'})

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert payload['item_name'] == pizza.name
    assert payload['quantity'] == 3
    assert payload['cart_count'] == 3
    # Verify calculated unit price with modifiers: Large (+$6.50) + Cauliflower Crust (+$2.50)
    expected_unit = round(pizza.base_price + 6.50 + 2.50, 2)
    assert payload['unit_price'] == expected_unit
    assert payload['line_total'] == round(expected_unit * 3, 2)
    assert payload['cart_subtotal'] == round(expected_unit * 3, 2)
    assert f'Added {pizza.name} to cart.' in payload['message']


def test_t1_03_catering_volume_fulfillment_estimates(client):
    """T1-03 / T1-04: Validate dynamic fulfillment prep times scale realistically with order volume."""
    pizza = MenuItem.query.filter(MenuItem.category.has(slug='specialty-pizzas'), MenuItem.is_available == True).first()
    assert pizza is not None

    # 1. Standard Order (2 items): 20-25m pickup, 40-50m delivery, no catering alert
    client.post('/cart/clear')
    client.post('/cart/add', data={'menu_item_id': pizza.id, 'quantity': 2})
    calc_res = client.post('/cart/calculate-api', json={'order_type': 'pickup'})
    calc_data = calc_res.get_json()
    assert calc_data['success'] is True
    est_std = calc_data['totals']['estimates']
    assert est_std['tier'] == 'standard'
    assert est_std['is_catering'] is False
    assert est_std['pickup_time'] == '20-25 mins'
    assert est_std['delivery_time'] == '40-50 mins'
    assert est_std['notice'] is None

    # 2. Medium Group Order (8 items): 35-45m pickup, 50-65m delivery
    client.post('/cart/clear')
    client.post('/cart/add', data={'menu_item_id': pizza.id, 'quantity': 8})
    calc_res8 = client.post('/cart/calculate-api', json={'order_type': 'pickup'})
    est_med = calc_res8.get_json()['totals']['estimates']
    assert est_med['tier'] == 'medium'
    assert est_med['is_catering'] is False
    assert est_med['pickup_time'] == '35-45 mins'
    assert est_med['delivery_time'] == '50-65 mins'
    assert 'Group Order Notice' in est_med['notice']

    # 3. High-Volume / Catering Order (50 items): 60-90+m pickup, 75-100+m delivery, active catering warning
    client.post('/cart/clear')
    client.post('/cart/add', data={'menu_item_id': pizza.id, 'quantity': 50})
    calc_res50 = client.post('/cart/calculate-api', json={'order_type': 'delivery'})
    est_cat = calc_res50.get_json()['totals']['estimates']
    assert est_cat['tier'] == 'catering'
    assert est_cat['is_catering'] is True
    assert est_cat['pickup_time'] == '60-90+ mins'
    assert est_cat['delivery_time'] == '75-100+ mins'
    assert 'High-Volume Order Notice' in est_cat['notice']

    # 4. Verify checkout screen renders the catering alert box and dynamic times
    checkout_res = client.get('/cart/checkout')
    checkout_html = checkout_res.data.decode('utf-8')
    assert 'catering-notice-box' in checkout_html
    assert '60-90+ mins' in checkout_html
    assert 'High-Volume / Catering Order' in checkout_html

    # 5. Verify confirmation screen carries over accurate catering timing and call-ahead notice
    submit_res = client.post('/order/submit', data={
        'customer_name': 'Jane Doe Catering',
        'customer_email': 'jane@example.com',
        'customer_phone': '(555) 392-4920',
        'order_type': 'delivery',
        'delivery_address': '123 Campus Blvd, Hall 4'
    }, follow_redirects=True)
    assert submit_res.status_code == 200
    confirm_html = submit_res.data.decode('utf-8')
    assert '75-100+ mins' in confirm_html
    assert 'High-Volume / Catering Order' in confirm_html


def test_t1_03_cart_inline_note_update(client):
    """T1-03: Validate inline special instructions editing directly from cart table."""
    pizza = MenuItem.query.filter(MenuItem.category.has(slug='specialty-pizzas'), MenuItem.is_available == True).first()
    assert pizza is not None

    client.post('/cart/clear')
    client.post('/cart/add', data={
        'menu_item_id': pizza.id,
        'quantity': 1,
        'special_notes': 'Initial note'
    })

    # 1. Update note via AJAX
    res = client.post('/cart/update-note', data={
        'index': 0,
        'special_notes': 'Well done crust with extra oregano on top'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})

    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['special_notes'] == 'Well done crust with extra oregano on top'

    # Verify session persisted
    with client.session_transaction() as sess:
        assert sess['cart'][0]['special_notes'] == 'Well done crust with extra oregano on top'

    # 2. Defensive truncation: 250 characters truncated to MAX_NOTES_LENGTH (200)
    long_note = 'A' * 250
    res_long = client.post('/cart/update-note', data={
        'index': 0,
        'special_notes': long_note
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res_long.status_code == 200
    data_long = res_long.get_json()
    assert len(data_long['special_notes']) == 200

    # 3. Clear note by sending empty string
    res_clear = client.post('/cart/update-note', data={
        'index': 0,
        'special_notes': '   '
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res_clear.status_code == 200
    assert res_clear.get_json()['special_notes'] is None

    # 4. Invalid index boundary test
    res_invalid = client.post('/cart/update-note', data={
        'index': 999,
        'special_notes': 'Invalid item'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res_invalid.status_code == 400
    assert res_invalid.get_json()['success'] is False

    # 5. Verify cart.html template renders inline form hooks
    cart_res = client.get('/cart/')
    cart_html = cart_res.data.decode('utf-8')
    assert 'cart-inline-note-form' in cart_html
    assert 'cart-note-container' in cart_html

def test_t1_03_cart_topping_customization_and_pricing(client):
    """T1-03 & T1-04: Test pizza topping customization, dynamic price calculation, distinct line separation, and order persistence."""
    item = MenuItem.query.filter_by(name='Pepperoni Rustica').first()
    assert item is not None
    options = item.get_options()
    assert 'toppings' in options
    assert len(options['toppings']) == 11
    assert any(t['name'] == 'Wisconsin Brick Cheese' for t in options['toppings'])

    # 1. Add pizza with Large (+6.50), Stuffed Crust (+3.00), and 2 toppings (Pepperoni $1.50 + Extra Mozzarella $1.50)
    # Expected unit price: 16.99 + 6.50 + 3.00 + 1.50 + 1.50 = 29.49
    res1 = client.post('/cart/add', data={
        'menu_item_id': item.id,
        'size_option': 'Large (16")',
        'crust_option': 'Garlic Herb Stuffed Crust',
        'toppings': ['Pepperoni', 'Extra Whole Milk Mozzarella'],
        'quantity': 2
    }, follow_redirects=True)
    assert res1.status_code == 200
    cart_html1 = res1.data.decode('utf-8')
    assert '$58.98' in cart_html1
    assert 'Extra Whole Milk Mozzarella' in cart_html1
    assert 'Pepperoni' in cart_html1

    # 2. Add second pizza with DIFFERENT toppings including Wisconsin Brick Cheese -> Must remain distinct line item
    res2 = client.post('/cart/add', data={
        'menu_item_id': item.id,
        'size_option': 'Large (16")',
        'crust_option': 'Garlic Herb Stuffed Crust',
        'toppings': ['Roasted Mushrooms', 'Wisconsin Brick Cheese'],
        'quantity': 1
    }, follow_redirects=True)
    cart_html2 = res2.data.decode('utf-8')
    assert 'Roasted Mushrooms' in cart_html2
    assert 'Wisconsin Brick Cheese' in cart_html2
    # Verify both line items are present
    assert cart_html2.count('<tr class="cart-row"') == 2

    # 3. Add identical configuration to first item -> Must merge quantity (2 + 1 = 3)
    res3 = client.post('/cart/add', data={
        'menu_item_id': item.id,
        'size_option': 'Large (16")',
        'crust_option': 'Garlic Herb Stuffed Crust',
        'toppings': ['Extra Whole Milk Mozzarella', 'Pepperoni'],  # Tested in reverse order
        'quantity': 1
    }, follow_redirects=True)
    cart_html3 = res3.data.decode('utf-8')
    # Should still only be 2 rows in cart table
    assert cart_html3.count('<tr class="cart-row"') == 2
    # Quantity for first item should now be 3, subtotal for item 3 * 29.49 = 88.47
    assert '$88.47' in cart_html3

    # 4. Submit order and verify persistence in OrderItem model and receipts
    submit_res = client.post('/order/submit', data={
        'customer_name': 'Kellen Jones',
        'customer_email': 'kjones@example.com',
        'customer_phone': '(555) 987-6543',
        'order_type': 'pickup'
    }, follow_redirects=True)
    assert submit_res.status_code == 200
    confirm_html = submit_res.data.decode('utf-8')
    assert '+ Toppings:' in confirm_html

    # Check database OrderItem
    from app.models import Order
    latest_order = Order.query.order_by(Order.id.desc()).first()
    assert latest_order is not None
    toppings_saved = [i.toppings for i in latest_order.items if i.toppings]
    assert len(toppings_saved) == 2
    assert any('Extra Whole Milk Mozzarella' in t for t in toppings_saved)
    assert any('Wisconsin Brick Cheese' in t for t in toppings_saved)

    # 5. Check staff orders dashboard displays toppings
    staff_res = client.get('/staff/orders')
    assert staff_res.status_code == 200
    assert '+ Toppings:' in staff_res.data.decode('utf-8')






