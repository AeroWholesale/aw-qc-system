import os
import importlib

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_socketio import SocketIO

from config.settings import config_by_name

db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    # Use gevent in production (gunicorn), fall back to threading in dev
    try:
        import gevent  # noqa: F401
        async_mode = "gevent"
    except ImportError:
        async_mode = "threading"
    socketio.init_app(app, cors_allowed_origins="*", async_mode=async_mode)

    from app.routes.main import main_bp
    from app.routes.devices import devices_bp
    from app.routes.tests import tests_bp
    from app.routes.station import station_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(devices_bp, url_prefix="/api/devices")
    app.register_blueprint(tests_bp, url_prefix="/api/tests")
    app.register_blueprint(station_bp, url_prefix="/api/station")

    importlib.import_module("app.events")

    return app
