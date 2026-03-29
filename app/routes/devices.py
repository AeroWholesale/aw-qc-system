from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from app import db, socketio
from app.models.device import Device

devices_bp = Blueprint("devices", __name__)


@devices_bp.route("/", methods=["GET"])
def list_devices():
    devices = Device.query.order_by(Device.created_at.desc()).all()
    return jsonify([d.to_dict() for d in devices])


@devices_bp.route("/stats", methods=["GET"])
def stats():
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    devices_today = Device.query.filter(Device.created_at >= today).all()
    total = len(devices_today)
    passed = sum(1 for d in devices_today if d.status == "passed")
    failed = sum(1 for d in devices_today if d.status == "failed")
    return jsonify({
        "total": total,
        "pending": sum(1 for d in devices_today if d.status == "pending"),
        "testing": sum(1 for d in devices_today if d.status == "testing"),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / (passed + failed) * 100) if (passed + failed) > 0 else 0,
    })


@devices_bp.route("/", methods=["POST"])
def create_device():
    data = request.get_json()
    device = Device(
        serial_number=data["serial_number"],
        device_type=data["device_type"],
        model=data["model"],
    )
    db.session.add(device)
    db.session.commit()
    socketio.emit("device_registered", device.to_dict(), room="dashboard")
    return jsonify(device.to_dict()), 201


@devices_bp.route("/<int:device_id>", methods=["GET"])
def get_device(device_id):
    device = db.get_or_404(Device, device_id)
    return jsonify(device.to_dict())


@devices_bp.route("/<int:device_id>", methods=["PATCH"])
def update_device(device_id):
    device = db.get_or_404(Device, device_id)
    data = request.get_json()
    for field in ("status", "station_id", "tested_by", "notes", "grade",
                   "grade_description", "battery_health", "cycle_count",
                   "ram", "storage", "model", "model_id"):
        if field in data:
            setattr(device, field, data[field])
    db.session.commit()
    socketio.emit("device_update", device.to_dict(), room="dashboard")
    return jsonify(device.to_dict())


@devices_bp.route("/detect", methods=["POST"])
def detect_device():
    data = request.get_json()
    serial = data["serial_number"]
    existing = Device.query.filter_by(serial_number=serial).first()
    if existing:
        return jsonify({
            "device": existing.to_dict(),
            "existing": True,
            "warning": f"Device already in system (status: {existing.status})",
        })
    device = Device(
        serial_number=serial,
        device_type=data.get("device_type", "macbook"),
        model=data.get("model", "Unknown"),
        station_id=data.get("station_id"),
        tested_by=data.get("tested_by"),
    )
    db.session.add(device)
    db.session.commit()
    socketio.emit("device_registered", device.to_dict(), room="dashboard")
    return jsonify({"device": device.to_dict(), "existing": False}), 201
