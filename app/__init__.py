from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache
import os
from config import Config

db = SQLAlchemy()
migrate = Migrate()
cache = Cache()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)

    # Register blueprints
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    # Create upload folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Create tables if not exist
    with app.app_context():
        db.create_all()

    return app
