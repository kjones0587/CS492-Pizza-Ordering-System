import pytest
from datetime import datetime, timezone
from app.models import db, Order, MenuItem, Category, Manager

def test_staff_menu_item_creation_and_info_update(client):
    """Verify managers can create new menu items and update descriptions (PB-08: Nicholas Lattimore)."""
    # 1. Authenticate as manager
    with client.session_transaction() as sess:
        sess['staff_user_id'] = 1
        sess['staff_username'] = 'manager'
        sess['staff_role'] = 'Store Manager'

    # Get a valid category
    category = Category.query.filter_by(slug='specialty-pizzas').first()
    if not category:
        category = Category(name='Specialty Pizzas', slug='specialty-pizzas', display_order=1)
        db.session.add(category)
        db.session.commit()

    # 2. POST create new menu item
    create_res = client.post('/staff/menu/create', data={
        'name': 'Wednesday Artisan Truffle Pizza',
        'category_id': category.id,
        'base_price': '22.95',
        'description': 'White truffle oil, wild forest mushrooms, and creamy fior di latte.',
        'is_available': 'on'
    }, follow_redirects=True)
    assert create_res.status_code == 200
    create_html = create_res.data.decode('utf-8')
    assert 'Wednesday Artisan Truffle Pizza' in create_html
    assert 'Successfully added' in create_html

    # Verify in database
    created_item = MenuItem.query.filter_by(name='Wednesday Artisan Truffle Pizza').first()
    assert created_item is not None
    assert created_item.base_price == 22.95
    assert created_item.is_available is True
    assert 'truffle' in created_item.description.lower()

    # 3. POST update item info / description
    update_res = client.post(f'/staff/menu/{created_item.id}/update-info', data={
        'name': 'Wednesday Truffle & Porcini Deluxe',
        'description': 'Updated recipe with Italian porcini mushrooms and aged parmigiano reggiano.'
    }, follow_redirects=True)
    assert update_res.status_code == 200
    db.session.refresh(created_item)
    assert created_item.name == 'Wednesday Truffle & Porcini Deluxe'
    assert 'porcini' in created_item.description.lower()

    # 4. Validation: reject negative or zero price
    bad_price_res = client.post('/staff/menu/create', data={
        'name': 'Free Pizza Defect',
        'category_id': category.id,
        'base_price': '-5.00'
    }, follow_redirects=True)
    assert 'Please enter a valid positive base price' in bad_price_res.data.decode('utf-8')


def test_kitchen_order_search_and_1_click_advance(client):
    """Verify staff can search orders and advance stages with 1-click bump bar (PB-05/PB-07: Michael Fabacher)."""
    # 1. Create distinct test orders
    order1 = Order(
        order_number='ORD-20260923-SEARCH1',
        customer_name='Searchable Customer A',
        customer_email='searcha@example.com',
        customer_phone='(555) 888-1111',
        order_type='pickup',
        subtotal=18.00,
        tax_amount=1.49,
        delivery_fee=0.0,
        total_amount=19.49,
        status='Received',
        created_at=datetime.now(timezone.utc),
        payment_method='cash',
        payment_status='Pending'
    )
    order2 = Order(
        order_number='ORD-20260923-SEARCH2',
        customer_name='Unique Name B',
        customer_email='uniqueb@example.com',
        customer_phone='(555) 999-2222',
        order_type='delivery',
        delivery_address='123 Campus Way',
        subtotal=30.00,
        tax_amount=2.48,
        delivery_fee=4.99,
        total_amount=37.47,
        status='Preparing',
        created_at=datetime.now(timezone.utc),
        payment_method='credit_card',
        payment_status='Paid'
    )
    db.session.add_all([order1, order2])
    db.session.commit()

    with client.session_transaction() as sess:
        sess['staff_user_id'] = 1
        sess['staff_username'] = 'manager'

    # 2. Test search by customer name
    search_res = client.get('/staff/orders?q=Searchable+Customer')
    assert search_res.status_code == 200
    search_html = search_res.data.decode('utf-8')
    assert 'ORD-20260923-SEARCH1' in search_html
    assert 'ORD-20260923-SEARCH2' not in search_html

    # 3. Test search by order number
    num_search = client.get('/staff/orders?q=SEARCH2')
    num_html = num_search.data.decode('utf-8')
    assert 'ORD-20260923-SEARCH2' in num_html
    assert 'ORD-20260923-SEARCH1' not in num_html

    # 4. Test 1-click stage advancement pipeline (Bump Bar)
    # Order 1: Received -> Preparing
    adv1 = client.post(f'/staff/orders/{order1.id}/advance', follow_redirects=True)
    assert adv1.status_code == 200
    db.session.refresh(order1)
    assert order1.status == 'Preparing'

    # Order 1: Preparing -> Baking
    adv2 = client.post(f'/staff/orders/{order1.id}/advance', follow_redirects=True)
    db.session.refresh(order1)
    assert order1.status == 'Baking'

    # Order 1: Baking -> Ready
    adv3 = client.post(f'/staff/orders/{order1.id}/advance', follow_redirects=True)
    db.session.refresh(order1)
    assert order1.status == 'Ready'

    # Order 1: Ready -> Completed
    adv4 = client.post(f'/staff/orders/{order1.id}/advance', follow_redirects=True)
    db.session.refresh(order1)
    assert order1.status == 'Completed'


def test_customer_order_feedback_and_rating(client):
    """Verify customer experience star rating and feedback on completed orders (PB-10: Ayden Lotter)."""
    order = Order(
        order_number='ORD-20260923-REVIEW1',
        customer_name='Food Critic',
        customer_email='critic@example.com',
        customer_phone='(555) 444-3333',
        order_type='pickup',
        subtotal=25.00,
        tax_amount=2.06,
        delivery_fee=0.0,
        total_amount=27.06,
        status='Completed',
        created_at=datetime.now(timezone.utc),
        payment_method='cash',
        payment_status='Pending'
    )
    db.session.add(order)
    db.session.commit()

    # 1. View completed order tracker -> verify rating form is rendered
    track_res = client.get(f'/order/{order.order_number}/track')
    assert track_res.status_code == 200
    track_html = track_res.data.decode('utf-8')
    assert 'How was your meal?' in track_html
    assert 'Submit Review' in track_html
    assert 'shareTrackerBtn' in track_html

    # 2. Submit 5-star review
    feedback_res = client.post(f'/order/{order.order_number}/feedback', data={
        'rating': '5',
        'feedback_text': 'Best wood-fired crust in town! Crispy, smoky, and absolutely delicious.'
    }, follow_redirects=True)
    assert feedback_res.status_code == 200
    feedback_html = feedback_res.data.decode('utf-8')
    assert 'Thank you for rating your meal' in feedback_html

    # 3. Refresh database and verify fields persisted
    db.session.refresh(order)
    assert order.customer_rating == 5
    assert 'Best wood-fired crust' in order.customer_feedback

    # 4. View tracker again -> verify feedback submitted badge and stars render
    after_res = client.get(f'/order/{order.order_number}/track')
    after_html = after_res.data.decode('utf-8')
    assert 'Feedback Submitted' in after_html
    assert '5 / 5 Stars' in after_html
    assert 'Best wood-fired crust in town' in after_html
