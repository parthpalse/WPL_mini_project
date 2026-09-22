import os

try:
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from flask_login import LoginManager

    db = SQLAlchemy()
    login_manager = LoginManager()
except ImportError:
    Flask = None
    db = None
    login_manager = None


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

    if config_override:
        app.config.update(config_override)

    # Validate configurations at startup
    from app.config_schema import validate_all_configs
    validate_all_configs(app.config['CONFIG_DIR'])

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'profile.login'

    # Register blueprints
    from app.routes.profile import profile_bp
    from app.routes.plan import plan_bp
    from app.routes.dashboard import dashboard_bp
    app.register_blueprint(profile_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(dashboard_bp)

    # Create tables
    with app.app_context():
        from app.models import models  # noqa: F401
        db.create_all()

    return app
