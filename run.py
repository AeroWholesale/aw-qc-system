from dotenv import load_dotenv

load_dotenv()

from app import create_app, db, socketio
from app.services.test_definitions import seed_defaults

app = create_app()

with app.app_context():
    db.create_all()
    seed_defaults()

if __name__ == "__main__":
    import os
    debug = os.environ.get("FLASK_ENV", "development") != "production"
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
