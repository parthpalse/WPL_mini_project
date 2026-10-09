import os

try:
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from flask_login import LoginManager
    from flask_wtf.csrf import CSRFProtect
    from flask_migrate import Migrate
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    db = SQLAlchemy()
    login_manager = LoginManager()
    csrf = CSRFProtect()
    migrate = Migrate()
    limiter = Limiter(key_func=get_remote_address)
except ImportError:
    Flask = None
    db = None
    login_manager = None
    csrf = None
    migrate = None
    limiter = None


def create_app(config_override=None):
    if Flask is None:
        raise RuntimeError("Flask is required to run the web application.")

    app = Flask(__name__)

    # Default config
    basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(basedir, "bankease.db")}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['CONFIG_DIR'] = os.path.join(basedir, 'config')

    # Session Security
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    if os.environ.get('FLASK_ENV') == 'production':
        app.config['SESSION_COOKIE_SECURE'] = True

    if config_override:
        app.config.update(config_override)

    # Validate configurations at startup
    from app.config_schema import validate_all_configs
    validate_all_configs(app.config['CONFIG_DIR'])

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    if limiter:
        limiter.init_app(app)

    from app.models.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Secure Headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # Setup Logging
    from app.logger import setup_logging
    setup_logging(app)
    
    # Error handlers
    from flask import render_template
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f'Server Error: {e}')
        return render_template('errors/500.html'), 500

    # ── Jinja2 Filters & Globals ──────────────────────────────────────────────
    def indian_currency(value):
        """Format a number as Indian currency string: ₹1,50,000"""
        try:
            n = abs(int(float(value)))
        except (TypeError, ValueError):
            return '₹0'
        s = str(n)
        last3 = s[-3:]
        rest = s[:-3]
        grouped = ','.join([rest[max(0, i-2):i] for i in range(len(rest), 0, -2)][::-1])
        return '₹' + ((grouped + ',') if grouped else '') + last3

    app.jinja_env.filters['indian_currency'] = indian_currency
    app.jinja_env.globals['abs'] = abs

    # Register blueprints
    from app.routes.spa import spa_bp
    from app.routes.api import api_bp
    from app.routes.profile import profile_bp, root_bp
    from app.routes.plan import plan_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.wizard import wizard_bp
    from app.routes.chat import chat_bp
    from app.routes.auth import auth_bp
    
    app.register_blueprint(spa_bp)
    app.register_blueprint(api_bp)
    csrf.exempt(api_bp)
    app.register_blueprint(root_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(wizard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    csrf.exempt(chat_bp)  # SSE streaming + CSRF form tokens are unreliable

    return app
