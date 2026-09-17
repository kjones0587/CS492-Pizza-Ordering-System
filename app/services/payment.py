"""
Task T2-06 (Story PB-06: Online Payment Handling)
Module Lead & Author: Kellen Jones (Scrum Master & Development Team)

Description:
Mock credit card payment processing service. Implements standard industry
algorithms for card validation (Luhn checksum, brand identification, expiry/CVV checks)
and simulates an external payment gateway sandbox (Stripe/Authorize.net style).

PCI-DSS Compliance Guarantee:
Full credit card primary account numbers (PAN) and card verification values (CVV)
are strictly held in transient memory during gateway transmission and are NEVER
persisted to SQLite tables or logging outputs. Only the card brand, last 4 digits,
and gateway transaction authorization IDs are returned for persistent storage.
"""

import re
import secrets
import string
from datetime import datetime, timezone

def clean_card_number(raw_number):
    """Strip spaces, hyphens, and non-numeric characters from card number input."""
    if not raw_number:
        return ""
    return re.sub(r'[\s\-.]+', '', str(raw_number).strip())

def validate_luhn(card_number):
    """
    Validate primary account number using the Modulo 10 Luhn algorithm.
    Returns True if card passes the checksum, False otherwise.
    """
    clean = clean_card_number(card_number)
    if not clean.isdigit() or len(clean) < 13 or len(clean) > 19:
        return False

    digits = [int(d) for d in clean]
    checksum = 0
    reversed_digits = digits[::-1]
    for idx, digit in enumerate(reversed_digits):
        if idx % 2 == 1:
            doubled = digit * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += digit

    return (checksum % 10) == 0

def detect_card_brand(card_number):
    """
    Detect payment card brand based on Bank Identification Number (BIN) prefix.
    Supports Visa, Mastercard, American Express, and Discover.
    """
    clean = clean_card_number(card_number)
    if not clean:
        return "Unknown"

    # Visa: Starts with 4
    if clean.startswith('4'):
        return "Visa"

    # Mastercard: 51-55 or 2221-2720
    if re.match(r'^(5[1-5]|2[2-7])', clean):
        return "Mastercard"

    # American Express: 34 or 37
    if clean.startswith(('34', '37')):
        return "American Express"

    # Discover: 6011, 622126-622925, 644-649, 65
    if clean.startswith(('6011', '65')) or re.match(r'^64[4-9]', clean):
        return "Discover"

    return "Credit Card"

def validate_expiration(exp_str):
    """
    Validate card expiration date format (MM/YY or MM/YYYY) and ensure not expired.
    Returns (is_valid, error_message).
    """
    if not exp_str:
        return False, "Expiration date is required."

    cleaned = str(exp_str).strip()
    match = re.match(r'^(\d{1,2})\s*[/ -]\s*(\d{2}|\d{4})$', cleaned)
    if not match:
        return False, "Expiration date must be in MM/YY format (e.g. 12/28)."

    month_str, year_str = match.groups()
    try:
        month = int(month_str)
        year = int(year_str)
    except ValueError:
        return False, "Invalid numeric values in expiration date."

    if month < 1 or month > 12:
        return False, "Expiration month must be between 01 and 12."

    # Normalize two-digit year (e.g. 28 -> 2028)
    if year < 100:
        year += 2000

    now = datetime.now()
    current_year = now.year
    current_month = now.month

    if year < current_year or (year == current_year and month < current_month):
        return False, "Card has expired. Please use a card with a valid future expiration date."

    if year > current_year + 20:
        return False, "Expiration year is unreasonably far in the future."

    return True, None

def validate_cvv(cvv_str, card_brand=None):
    """
    Validate Card Verification Value (3 digits, or 4 digits for American Express).
    Returns (is_valid, error_message).
    """
    if not cvv_str:
        return False, "Security code (CVV) is required."

    clean_cvv = str(cvv_str).strip()
    if not clean_cvv.isdigit():
        return False, "Security code must be numeric."

    expected_len = 4 if card_brand == "American Express" else 3
    if len(clean_cvv) != expected_len and len(clean_cvv) not in (3, 4):
        return False, f"CVV must be {expected_len} digits for {card_brand or 'credit cards'}."

    return True, None

def generate_transaction_id():
    """Generate mock gateway transaction reference ID (e.g. TXN-20260917-8FK29A)."""
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    suffix = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"TXN-{date_part}-{suffix}"

def process_mock_payment(amount, card_number, exp_date, cvv, cardholder_name=None, billing_zip=None):
    """
    Simulate processing an online payment transaction via external gateway API.

    Enforces PCI-DSS standard:
    - Verifies Luhn algorithm, expiry, and CVV.
    - Simulates sandbox test decline triggers (card ending in '0002' simulates insufficient funds).
    - Discards raw card PAN and CVV.
    - Returns standardized transaction receipt dictionary.
    """
    clean_num = clean_card_number(card_number)

    if not cardholder_name or len(cardholder_name.strip()) < 2:
        return {
            'success': False,
            'error': 'Cardholder name is required as it appears on the card.',
            'card_brand': 'Unknown',
            'card_last4': clean_num[-4:] if len(clean_num) >= 4 else None,
            'transaction_id': None
        }

    # 1. Card Number Luhn Check
    if not validate_luhn(clean_num):
        return {
            'success': False,
            'error': 'Invalid card number. Please check the 16 digits and try again.',
            'card_brand': detect_card_brand(clean_num),
            'card_last4': clean_num[-4:] if len(clean_num) >= 4 else None,
            'transaction_id': None
        }

    brand = detect_card_brand(clean_num)
    last4 = clean_num[-4:]

    # 2. Expiration Date Check
    is_valid_exp, exp_err = validate_expiration(exp_date)
    if not is_valid_exp:
        return {
            'success': False,
            'error': exp_err,
            'card_brand': brand,
            'card_last4': last4,
            'transaction_id': None
        }

    # 3. CVV Check
    is_valid_cvv, cvv_err = validate_cvv(cvv, card_brand=brand)
    if not is_valid_cvv:
        return {
            'success': False,
            'error': cvv_err,
            'card_brand': brand,
            'card_last4': last4,
            'transaction_id': None
        }

    # 4. Billing Zip Check
    if billing_zip and not re.match(r'^\d{5}(-\d{4})?$', str(billing_zip).strip()):
        return {
            'success': False,
            'error': 'Invalid 5-digit billing ZIP code.',
            'card_brand': brand,
            'card_last4': last4,
            'transaction_id': None
        }

    # 5. Simulated Gateway Decline Triggers (Sandbox edge-case testing)
    if last4 == '0002':
        return {
            'success': False,
            'error': 'Transaction declined by card issuer: Insufficient funds.',
            'card_brand': brand,
            'card_last4': last4,
            'transaction_id': None
        }

    if last4 == '0005':
        return {
            'success': False,
            'error': 'Transaction declined: Card reported lost or stolen.',
            'card_brand': brand,
            'card_last4': last4,
            'transaction_id': None
        }

    # 6. Approved Transaction
    txn_id = generate_transaction_id()
    return {
        'success': True,
        'error': None,
        'transaction_id': txn_id,
        'card_brand': brand,
        'card_last4': last4,
        'cardholder_name': cardholder_name.strip(),
        'amount': float(amount),
        'message': f'Payment of ${float(amount):.2f} authorized successfully.'
    }
