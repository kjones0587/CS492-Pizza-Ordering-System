from flask import Flask, session
from sqlalchemy import text
from app.config import Config
from app.models import db
from app.db_init import seed_database

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.menu import menu_bp
    from app.routes.cart import cart_bp
    from app.routes.order import order_bp
    from app.routes.staff import staff_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(menu_bp, url_prefix='/menu')
    app.register_blueprint(cart_bp, url_prefix='/cart')
    app.register_blueprint(order_bp, url_prefix='/order')
    app.register_blueprint(staff_bp, url_prefix='/staff')

    # Security Middleware & CSRF Protection (Task T2-10 / PB-11: Ayden Lotter)
    from app.security import generate_csrf_token, validate_csrf
    app.before_request(validate_csrf)

    # Context processors for all templates
    @app.context_processor
    def inject_global_data():
        cart = session.get('cart', [])
        cart_total_qty = sum(item.get('quantity', 1) for item in cart)
        restaurant_info = {
            'name': 'Bella Napoli Pizzeria',
            'tagline': 'Authentic Wood-Fired Artisan Pizza',
            'phone': '(555) 392-4920',
            'email': 'orders@bellanapolipizza.com',
            'address': '742 Evergreen Terrace, Campus District, Suite 101',
            'hours': [
                {'days': 'Monday - Thursday', 'time': '11:00 AM - 10:00 PM'},
                {'days': 'Friday - Saturday', 'time': '11:00 AM - 11:00 PM'},
                {'days': 'Sunday', 'time': '12:00 PM - 9:00 PM'}
            ]
        }
        return {
            'cart_count': cart_total_qty,
            'restaurant': restaurant_info,
            'csrf_token': generate_csrf_token
        }

    # Automatically create tables and seed on startup
    with app.app_context():
        db.create_all()
        # Auto-patch schema for existing development databases
        migration_statements = [
            "ALTER TABLE order_items ADD COLUMN toppings VARCHAR(255)",
            "ALTER TABLE orders ADD COLUMN payment_method VARCHAR(30) DEFAULT 'credit_card'",
            "ALTER TABLE orders ADD COLUMN payment_status VARCHAR(40) DEFAULT 'Paid'",
            "ALTER TABLE orders ADD COLUMN card_brand VARCHAR(30)",
            "ALTER TABLE orders ADD COLUMN card_last4 VARCHAR(4)",
            "ALTER TABLE orders ADD COLUMN transaction_id VARCHAR(64)",
            "ALTER TABLE orders ADD COLUMN discount_amount FLOAT DEFAULT 0.0",
            "ALTER TABLE orders ADD COLUMN promo_code VARCHAR(30)",
            "ALTER TABLE orders ADD COLUMN staff_notes VARCHAR(255)",
        ]
        with db.engine.connect() as conn:
            for stmt in migration_statements:
                try:
                    conn.execute(text(stmt))
                    conn.commit()
                except Exception:
                    pass  # Column already exists or freshly created
        seed_database()

    return app
