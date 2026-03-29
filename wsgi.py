from app import create_app, db, socketio
from app.services.test_definitions import seed_defaults

app = create_app("production")

with app.app_context():
    db.create_all()
    seed_defaults()
