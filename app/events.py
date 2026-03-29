from flask_socketio import join_room
from app import socketio


@socketio.on("join_dashboard")
def handle_join_dashboard():
    join_room("dashboard")


@socketio.on("join_station")
def handle_join_station(data):
    join_room(f"station_{data.get('station_id', 'unknown')}")
