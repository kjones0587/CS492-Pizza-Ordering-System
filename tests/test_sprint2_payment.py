"""
Task T2-06 / Story PB-06: Online Payment Processing Unit & Integration Test Suite
Author: Kellen Jones (Scrum Master & Development Team)

Comprehensive test coverage validating:
1. Luhn Modulo 10 card validation algorithm
2. BIN prefix card brand identification (Visa, Mastercard, Amex, Discover)
3. Expiration date parsing and future date enforcement
4. CVV length and character validation (3-4 digits)
5. Mock payment gateway sandbox transactions and decline triggers
6. Full checkout order placement with credit card authorization
7. Sandbox decline handling with user feedback
8. Zero-balance VIP pass waiver bypass
9. Strict PCI-DSS compliance verification (zero PAN / CVV persistence)
"""

import pytest
from app.models import db, Order, MenuItem
from app.services.payment import (
    clean_card_number,
    validate_luhn,
    detect_card_brand,
    validate_expiration,
    validate_cvv,
    process_mock_payment,
    generate_transaction_id
)

def test_luhn_algorithm_validation():
    # Valid cards
    assert validate_luhn("4242 4242 4242 4242") is True
    assert validate_luhn("4000-0000-0000-0002") is True
    assert validate_luhn("5555555555554444") is True
    assert validate_luhn("378282246310005") is True

    # Invalid checksum
    assert validate_luhn("4242 4242 4242 4243") is False
    assert validate_luhn("1234 5678 9012 3456") is False

    # Invalid lengths or characters
    assert validate_luhn("") is False
    assert validate_luhn("not-a-number") is False
    assert validate_luhn("12345") is False

def test_detect_card_brand():
    assert detect_card_brand("4242 4242 4242 4242") == "Visa"
    assert detect_card_brand("5105 1051 0510 5100") == "Mastercard"
    assert detect_card_brand("2221 0000 0000 0000") == "Mastercard"
    assert detect_card_brand("3782 8224 6310 005") == "American Express"
    assert detect_card_brand("3400 0000 0000 000") == "American Express"
    assert detect_card_brand("6011 0000 0000 0000") == "Discover"
    assert detect_card_brand("6500 0000 0000 0000") == "Discover"
    assert detect_card_brand("9999 9999 9999 9999") == "Credit Card"
    assert detect_card_brand("") == "Unknown"

def test_validate_expiration():
    # Valid future dates
    valid, err = validate_expiration("12/28")
    assert valid is True
    assert err is None

    valid, err = validate_expiration("01/2030")
    assert valid is True
    assert err is None

    # Past expiration dates
    valid, err = validate_expiration("01/20")
    assert valid is False
    assert "expired" in err.lower()

    # Invalid formatting or month ranges
    valid, err = validate_expiration("13/28")
    assert valid is False
    assert "between 01 and 12" in err.lower()

    valid, err = validate_expiration("invalid")
    assert valid is False
    assert "format" in err.lower()

def test_validate_cvv():
    # 3-digit standard for Visa / Mastercard
    valid, err = validate_cvv("123", card_brand="Visa")
    assert valid is True

    valid, err = validate_cvv("12", card_brand="Visa")
    assert valid is False

    # 4-digit for Amex
    valid, err = validate_cvv("1234", card_brand="American Express")
    assert valid is True

    valid, err = validate_cvv("123", card_brand="American Express")
    assert valid is False

    # Non-numeric
    valid, err = validate_cvv("abc")
    assert valid is False

def test_process_mock_payment_approved():
    result = process_mock_payment(
        amount=34.50,
        card_number="4242 4242 4242 4242",
        exp_date="12/28",
        cvv="123",
        cardholder_name="Dr. Fadi Almasri",
        billing_zip="90210"
    )
    assert result['success'] is True
    assert result['card_brand'] == "Visa"
    assert result['card_last4'] == "4242"
    assert result['amount'] == 34.50
    assert result['transaction_id'].startswith("TXN-")
    assert result['error'] is None

def test_process_mock_payment_declined_insufficient_funds():
    result = process_mock_payment(
        amount=25.00,
        card_number="4000 0000 0000 0002",
        exp_date="12/28",
        cvv="123",
        cardholder_name="Jane Decline",
        billing_zip="90210"
    )
    assert result['success'] is False
    assert "insufficient funds" in result['error'].lower()
    assert result['transaction_id'] is None

def test_process_mock_payment_declined_lost_or_stolen():
    result = process_mock_payment(
        amount=25.00,
        card_number="4000 0000 0007 0005",
        exp_date="12/28",
        cvv="123",
        cardholder_name="Jane Decline",
        billing_zip="90210"
    )
    assert result['success'] is False
    assert "lost or stolen" in result['error'].lower()

def test_order_submission_with_credit_card_integration(client, app):
    """End-to-end integration test of online credit card payment and order creation."""
    with app.app_context():
        item = MenuItem.query.first()
        item_id = item.id

    client.post('/cart/add', data={'menu_item_id': item_id, 'quantity': 2})

    res = client.post('/order/submit', data={
        'customer_name': 'Kellen Jones',
        'customer_email': 'kjones0587@gmail.com',
        'customer_phone': '(555) 987-6543',
        'order_type': 'delivery',
        'delivery_address': '456 University Ave, Apt 3B',
        'payment_method': 'credit_card',
        'name_on_card': 'Kellen Jones',
        'card_number': '4242 4242 4242 4242',
        'exp_date': '12/28',
        'cvv': '123',
        'billing_zip': '90210'
    }, follow_redirects=True)

    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert "Order Received!" in html
    assert "Visa ending in 4242" in html
    assert "Paid" in html
    assert "Ref: TXN-" in html

    # Verify database record and PCI compliance
    with app.app_context():
        order = Order.query.filter_by(customer_email='kjones0587@gmail.com').order_by(Order.id.desc()).first()
        assert order is not None
        assert order.payment_method == 'credit_card'
        assert order.payment_status == 'Paid'
        assert order.card_brand == 'Visa'
        assert order.card_last4 == '4242'
        assert order.transaction_id.startswith('TXN-')
        # Strict PCI Compliance: full card number must not appear in any order field
        assert "4242424242424242" not in str(order.__dict__)

def test_order_submission_with_declined_card_fails(client, app):
    """Ensure declined cards prevent order creation and flash an error."""
    with app.app_context():
        item = MenuItem.query.first()
        item_id = item.id
        initial_order_count = Order.query.count()

    client.post('/cart/add', data={'menu_item_id': item_id, 'quantity': 1})

    res = client.post('/order/submit', data={
        'customer_name': 'Test User',
        'customer_email': 'test@example.com',
        'customer_phone': '(555) 111-2222',
        'order_type': 'pickup',
        'special_instructions': 'Extra crispy crust, ring bell please.',
        'payment_method': 'credit_card',
        'name_on_card': 'Jane Decline',
        'card_number': '4000 0000 0000 0002',
        'exp_date': '12/28',
        'cvv': '123',
        'billing_zip': '90210'
    }, follow_redirects=True)

    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert "Payment Processing Error" in html
    assert "Insufficient funds" in html
    assert "Transaction Declined" in html
    assert "Card Declined" in html

    # Verify input data was strictly preserved in the form after card decline
    assert 'value="Test User"' in html
    assert 'value="test@example.com"' in html
    assert 'value="(555) 111-2222"' in html
    assert 'Extra crispy crust, ring bell please.' in html
    assert 'value="Jane Decline"' in html
    assert 'value="90210"' in html

    # Verify NO order was created
    with app.app_context():
        assert Order.query.count() == initial_order_count

def test_order_submission_with_cash(client, app):
    """Test cash payment order submission records correct pending status."""
    with app.app_context():
        item = MenuItem.query.first()
        item_id = item.id

    client.post('/cart/add', data={'menu_item_id': item_id, 'quantity': 1})

    res = client.post('/order/submit', data={
        'customer_name': 'Cash Buyer',
        'customer_email': 'cash@example.com',
        'customer_phone': '(555) 333-4444',
        'order_type': 'pickup',
        'payment_method': 'cash'
    }, follow_redirects=True)

    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert "Order Received!" in html
    assert "Cash on Pickup Counter" in html
    assert "Due on Pickup" in html

    with app.app_context():
        order = Order.query.filter_by(customer_email='cash@example.com').order_by(Order.id.desc()).first()
        assert order is not None
        assert order.payment_method == 'cash'
        assert 'Due' in order.payment_status

def test_order_submission_with_zero_balance_vip_waiver(client, app):
    """Verify that orders with promo code ALMASRI waive card requirement and record VIP Pass."""
    with app.app_context():
        item = MenuItem.query.first()
        item_id = item.id

    client.post('/cart/add', data={'menu_item_id': item_id, 'quantity': 1})
    client.post('/cart/apply-promo', data={'promo_code': 'ALMASRI'})

    res = client.post('/order/submit', data={
        'customer_name': 'Prof. Almasri',
        'customer_email': 'prof.almasri@bellanapolipizza.com',
        'customer_phone': '(555) 777-8888',
        'order_type': 'pickup',
        'payment_method': 'credit_card'  # Even if credit_card was checked, total $0 bypasses it
    }, follow_redirects=True)

    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert "VIP Faculty Pass (Complimentary)" in html

    with app.app_context():
        order = Order.query.filter_by(customer_email='prof.almasri@bellanapolipizza.com').order_by(Order.id.desc()).first()
        assert order is not None
        assert order.payment_method == 'vip_pass'
        assert order.total_amount == 0.0
        assert order.transaction_id.startswith('TXN-VIP-')

def test_checkout_2step_wizard_and_autofill_elements(client, app):
    """Verify that the checkout template renders the 2-step wizard and 1-click autofill buttons."""
    with app.app_context():
        item = MenuItem.query.first()
        item_id = item.id

    client.post('/cart/add', data={'menu_item_id': item_id, 'quantity': 1})
    res = client.get('/cart/checkout')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify 2-Step wizard stepper
    assert 'id="step-badge-1"' in html
    assert 'id="step-badge-2"' in html
    assert 'id="checkout-step-1"' in html
    assert 'id="checkout-step-2"' in html
    assert 'Continue to Payment &amp; Review' in html or 'Continue to Payment & Review' in html

    # Verify 1-click autofill buttons
    assert 'fillCustomerDemo()' in html
    assert 'Auto-Fill Demo Info' in html
    assert 'fillInstructionsDemo()' in html
    assert 'Sample Note' in html
    assert "fillDemoCard('valid')" in html
    assert 'Auto-Fill Demo Visa' in html
    assert "fillDemoCard('decline')" in html
    assert 'Test Decline Card' in html

    # Verify Step 2 summary capsule and payment fields
    assert 'id="summary-customer-name"' in html
    assert 'id="summary-fulfillment-type"' in html
    assert 'id="credit-card-fields"' in html
    assert 'name_on_card' in html
    assert 'card_number' in html
    assert 'exp_date' in html
    assert 'cvv' in html
    assert 'billing_zip' in html

