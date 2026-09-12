from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
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
