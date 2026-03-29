import sys
import os
from datetime import datetime

from flask import Blueprint, request, jsonify

from app import db, socketio
from app.models.device import Device
from app.services.grader import calculate_grade
from app.services.label_printer import generate_zpl, print_label

# Add mdm/ to path for wipe module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'mdm'))

station_bp = Blueprint("station_api", __name__)


@station_bp.route("/update", methods=["POST"])
def station_update():
    """Broadcast station status to dashboard and the specific station display."""
    data = request.get_json()
    station_id = data.get("station_id", "")
    socketio.emit("station_status", data, room="dashboard")
    socketio.emit("station_status", data, room=f"station_{station_id}")
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


@station_bp.route("/wipe", methods=["POST"])
def wipe_device_endpoint():
    """Wipe a device via MDM or cfgutil fallback."""
    data = request.get_json()
    device_id = data.get("device_id")

    if not device_id:
        return jsonify({"ok": False, "error": "device_id required"}), 400

    device = Device.query.get(device_id)
    if not device:
        return jsonify({"ok": False, "error": "Device not found"}), 404

    # Broadcast wipe started
    socketio.emit("wipe_status", {
        "device_id": device_id,
        "status": "sending",
        "message": "Sending wipe command...",
    })

    try:
        from wipe import wipe_device
        result = wipe_device(
            device_udid=data.get("udid"),
            ecid=data.get("ecid"),
        )
    except ImportError:
        result = {"ok": False, "error": "Wipe module not available"}

    if result.get("ok"):
        socketio.emit("wipe_status", {
            "device_id": device_id,
            "status": "erasing",
            "message": "Device erasing...",
        })
        device.status = "wiped"
        db.session.commit()
    else:
        socketio.emit("wipe_status", {
            "device_id": device_id,
            "status": "failed",
            "message": f"Wipe failed: {result.get('error', 'Unknown error')}",
        })

    return jsonify(result)
