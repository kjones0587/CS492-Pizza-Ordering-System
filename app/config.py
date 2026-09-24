import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-cs492-capstone-secret-key-2026')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BASE_DIR, 'pizza.db')}"
    )
    # Tax rate: 8.25%
    TAX_RATE = 0.0825
    # Standard delivery fee
    DELIVERY_FEE = 4.99

    # SQLite Concurrency & Timeout Hardening
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'timeout': 30}
    }

    # Security & Cookie Hardening (Task T2-10 / PB-11: Ayden Lotter)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
