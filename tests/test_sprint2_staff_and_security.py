import pytest
from app.models import db, MenuItem, Category, Manager

def test_staff_menu_view_and_metrics(client):
    """PB-08 (Nicholas Lattimore): Verify staff menu management dashboard loads item listings and metrics."""
    res = client.get('/staff/menu')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'Menu Item Management' in html
    assert 'Total Menu Items' in html
    assert 'In Stock / Available' in html
    assert 'Sold Out / Unavailable' in html
    assert 'Margherita Classico' in html
    assert 'Pepperoni Rustica' in html

def test_staff_menu_toggle_item_availability(client):
    """PB-08 (Nicholas Lattimore): Verify 1-click availability toggling updates database and customer menu."""
    item = MenuItem.query.filter_by(name='Margherita Classico').first()
    assert item is not None
    initial_status = item.is_available

    # 1. Toggle status via POST
    toggle_res = client.post(f'/staff/menu/{item.id}/toggle-status', follow_redirects=True)
    assert toggle_res.status_code == 200

    # Verify DB updated
    updated_item = db.session.get(MenuItem, item.id)
    assert updated_item.is_available == (not initial_status)

    # 2. Verify customer menu reflects new status
    menu_res = client.get('/menu/')
    menu_html = menu_res.data.decode('utf-8')
    if not updated_item.is_available:
        assert 'Currently Unavailable' in menu_html or 'Sold Out' in menu_html

    # 3. Toggle back to original status
    client.post(f'/staff/menu/{item.id}/toggle-status', follow_redirects=True)
    restored_item = db.session.get(MenuItem, item.id)
    assert restored_item.is_available == initial_status

def test_staff_route_protection_and_login_flow(client, app):
    """PB-07 (Michael Fabacher): Verify route protection, redirect-after-login, and authentication lifecycle."""
    # Enable TESTING_AUTH to enforce decorator checks in test environment
    app.config['TESTING_AUTH'] = True
    try:
        # 1. Unauthenticated request to /staff/orders should redirect to /staff/login
        res_unauth = client.get('/staff/orders')
        assert res_unauth.status_code == 302
        assert '/staff/login' in res_unauth.headers['Location']

        # 2. Login with incorrect password fails
        res_fail = client.post('/staff/login', data={
            'username': 'manager',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert res_fail.status_code == 200
        assert 'Invalid username or password' in res_fail.data.decode('utf-8')

        # 3. Login with valid manager credentials succeeds
        res_login = client.post('/staff/login', data={
            'username': 'manager',
            'password': 'pizza123'
        }, follow_redirects=True)
        assert res_login.status_code == 200
        assert 'Welcome back, manager!' in res_login.data.decode('utf-8')
        assert 'Incoming Orders Dashboard' in res_login.data.decode('utf-8')

        # 4. Authenticated request to /staff/menu succeeds
        res_menu = client.get('/staff/menu')
        assert res_menu.status_code == 200
        assert 'Menu Item Management' in res_menu.data.decode('utf-8')

        # 5. Logout clears session
        res_logout = client.get('/staff/logout', follow_redirects=True)
        assert res_logout.status_code == 200
        assert 'You have been logged out' in res_logout.data.decode('utf-8')

        # 6. Subsequent request is redirected again
        res_after = client.get('/staff/orders')
        assert res_after.status_code == 302
    finally:
        app.config['TESTING_AUTH'] = False

def test_checkout_pci_compliance_badge_and_accessibility(client):
    """PB-11 / PB-12 (Ayden Lotter): Verify PCI-DSS security trust badge, modal, and accessibility tags."""
    # Add an item to cart first
    item = MenuItem.query.filter_by(is_available=True).first()
    client.post('/cart/add', data={'menu_item_id': item.id, 'quantity': 1})

    res = client.get('/cart/checkout')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify PCI Trust Banner
    assert 'pci-trust-banner' in html
    assert 'PCI-DSS Compliant' in html
    assert '256-Bit SSL Encrypted' in html
    assert 'pciComplianceModal' in html

    # Verify Stepper Accessibility
    assert 'role="tablist"' in html
    assert 'aria-current="step"' in html
    assert 'aria-label="Step 1: Contact and Delivery Details"' in html
