from datetime import datetime

from flask import Blueprint, request, jsonify

from app import db, socketio
from app.models.device import Device
from app.services.grader import calculate_grade
from app.services.label_printer import generate_zpl, print_label

station_bp = Blueprint("station_api", __name__)


@station_bp.route("/update", methods=["POST"])
def station_update():
    """Broadcast station status to supervisor dashboard."""
    data = request.get_json()
    socketio.emit("station_status", data, room="dashboard")
    return jsonify({"ok": True})


@station_bp.route("/grade", methods=["POST"])
def grade_device():
    """Calculate grade from auto + manual check data."""
    data = request.get_json()
    grade, description, fail_reasons = calculate_grade(
        battery_health=data.get("battery_health"),
        cycle_count=data.get("cycle_count"),
        manual_checks=data.get("manual_checks", {}),
        auto_checks=data.get("auto_checks", {}),
    )
    return jsonify({
        "grade": grade,
        "description": description,
        "fail_reasons": fail_reasons,
    })


@station_bp.route("/diagnostics", methods=["POST"])
def receive_diagnostics():
    """Receive diagnostic data from agent.py running on the MacBook under test."""
    data = request.get_json()
    device_id = data.get("device_id")
    step = data.get("step")
    payload = data.get("data", {})

    # Persist key fields on the device record
    if device_id:
        device = Device.query.get(device_id)
        if device:
            if payload.get("model"):
                device.model = payload["model"]
            if payload.get("model_id"):
                device.model_id = payload["model_id"]
            if payload.get("battery_health") is not None:
                device.battery_health = payload["battery_health"]
            if payload.get("cycle_count") is not None:
                device.cycle_count = payload["cycle_count"]
            if payload.get("ram"):
                device.ram = payload["ram"]
            if payload.get("storage"):
                device.storage = payload["storage"]
            db.session.commit()

    # Broadcast to station displays
    socketio.emit("diagnostic_step", {
        "device_id": device_id,
        "step": step,
        "data": payload,
    })

    return jsonify({"ok": True})


@station_bp.route("/print", methods=["POST"])
def print_qc_label():
    """Generate ZPL and send to Zebra printer."""
    data = request.get_json()
    label_data = {
        "model": data.get("model", ""),
        "serial": data.get("serial", ""),
        "ram": data.get("ram", ""),
        "storage": data.get("storage", ""),
        "color": data.get("color", ""),
        "battery_health": data.get("battery_health", ""),
        "cycle_count": data.get("cycle_count", ""),
        "grade": data.get("grade", ""),
        "passed": data.get("passed", True),
        "fail_reason": data.get("fail_reason", ""),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "station": data.get("station", ""),
        "tech": data.get("tech", ""),
    }
    zpl = generate_zpl(label_data)

    result = print_label(zpl)
    result["zpl"] = zpl
    return jsonify(result)
