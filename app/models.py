from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=True)
    display_order = db.Column(db.Integer, default=0)

    menu_items = db.relationship('MenuItem', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'


class MenuItem(db.Model):
    __tablename__ = 'menu_items'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    base_price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    # Stored as JSON string e.g. {"sizes": [{"name": "Small (10\")", "price_mod": 0}, ...], "crusts": [...]}
    options_json = db.Column(db.Text, nullable=True)

    def get_options(self):
        if self.options_json:
            try:
                return json.loads(self.options_json)
            except Exception:
                return {}
        return {}

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'base_price': self.base_price,
            'image_url': self.image_url,
            'is_available': self.is_available,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else '',
            'options': self.get_options()
        }

    def __repr__(self):
        return f'<MenuItem {self.name}>'


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    customer_name = db.Column(db.String(120), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(30), nullable=False)
    order_type = db.Column(db.String(20), nullable=False, default='pickup')  # 'pickup' or 'delivery'
    delivery_address = db.Column(db.String(255), nullable=True)
    special_instructions = db.Column(db.Text, nullable=True)

    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    tax_amount = db.Column(db.Float, nullable=False, default=0.0)
    delivery_fee = db.Column(db.Float, nullable=False, default=0.0)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)

    status = db.Column(db.String(30), nullable=False, default='Received')  # Received, Preparing, Ready, Completed, Cancelled
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Sprint 2 (PB-06 & PB-09): Payment details and discounts
    payment_method = db.Column(db.String(30), nullable=False, default='credit_card')  # 'credit_card' or 'cash'
    payment_status = db.Column(db.String(40), nullable=False, default='Paid')  # 'Paid', 'Pending (Due on Pickup/Delivery)', 'Failed'
    card_brand = db.Column(db.String(30), nullable=True)  # 'Visa', 'Mastercard', 'American Express', 'Discover'
    card_last4 = db.Column(db.String(4), nullable=True)  # Last 4 digits only (PCI compliant)
    transaction_id = db.Column(db.String(64), nullable=True)  # Gateway reference e.g. TXN-20260916-XXXX
    discount_amount = db.Column(db.Float, nullable=False, default=0.0)
    promo_code = db.Column(db.String(30), nullable=True)

    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Order {self.order_number}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=True)
    item_name = db.Column(db.String(120), nullable=False)
    size_option = db.Column(db.String(50), nullable=True)
    crust_option = db.Column(db.String(50), nullable=True)
    toppings = db.Column(db.String(255), nullable=True)
    special_notes = db.Column(db.String(255), nullable=True)
    unit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    line_total = db.Column(db.Float, nullable=False)

    menu_item = db.relationship('MenuItem', backref='order_items', lazy=True)

    def __repr__(self):
        return f'<OrderItem {self.item_name} x{self.quantity}>'


# =============================================================================
# Sprint 2 Foundation Models
# =============================================================================

class Manager(db.Model):
    """Store Manager & Staff Accounts for Authentication (PB-07: Michael Fabacher)"""
    __tablename__ = 'managers'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(32), default='Store Manager', nullable=False)  # 'Store Manager', 'Kitchen Staff'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Manager {self.username}>'


class PromoCode(db.Model):
    """Promotional Discount Codes & Coupons (PB-09: Nicholas Lattimore)"""
    __tablename__ = 'promo_codes'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    description = db.Column(db.String(120), nullable=True)
    discount_type = db.Column(db.String(20), nullable=False, default='percent')  # 'percent' or 'fixed'
    discount_value = db.Column(db.Float, nullable=False)  # e.g., 10.0 for 10% off or 5.0 for $5.00 off
    min_subtotal = db.Column(db.Float, default=0.0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def calculate_discount(self, subtotal):
        if not self.is_active or subtotal < self.min_subtotal:
            return 0.0
        if self.discount_type == 'percent':
            discount = round(subtotal * (self.discount_value / 100.0), 2)
        elif self.discount_type == 'fixed':
            discount = min(round(self.discount_value, 2), subtotal)
        else:
            discount = 0.0
        return discount

    def __repr__(self):
        return f'<PromoCode {self.code}>'

