"""Flask app factory for the generalized Accounting Suite."""
import os
from flask import Flask
from . import database


def create_app():
    app = Flask(__name__)

    # Secret key for sessions
    # Generate a random key if undefined to prevent forged session cookies
    app.config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY', os.urandom(32).hex()
    )

    # Database path
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    app.config['DATABASE'] = os.path.join(data_dir, 'accounting.db')

    # Auth credentials from env
    app.config['AUTH_USERNAME'] = os.environ.get('AUTH_USERNAME', 'admin')
    app.config['AUTH_PASSWORD_HASH'] = os.environ.get('AUTH_PASSWORD_HASH', '')

    # Initialize database
    database.init_app(app)

    # Register auth
    from .auth import auth_bp, login_required_middleware
    app.register_blueprint(auth_bp)
    app.before_request(login_required_middleware)

    # Register route blueprints
    from .routes.dashboard_routes import dashboard_bp
    from .routes.import_routes import import_bp
    from .routes.transaction_routes import transaction_bp
    from .routes.settings_routes import settings_bp
    from .routes.invoice_routes import invoice_bp
    from .routes.report_routes import report_bp
    from .routes.tax_routes import tax_bp
    from .routes.health_routes import health_bp
    from .routes.contractor_routes import contractor_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(transaction_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(invoice_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(tax_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(contractor_bp)

    @app.context_processor
    def inject_business_profile():
        try:
            from .models import get_business_config
            bconfig = get_business_config()
            # Truncate for the sidebar <h1> if it's super long, but usually fine
            return dict(business_name=bconfig.get('business_name', 'My Business LLC'))
        except Exception:
            return dict(business_name='My Business LLC')

    return app
