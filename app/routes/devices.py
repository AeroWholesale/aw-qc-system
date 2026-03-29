from flask import Blueprint, request, jsonify

from app import db
from app.models.device import Device

devices_bp = Blueprint("devices", __name__)


@devices_bp.route("/", methods=["GET"])
def list_devices():
    devices = Device.query.order_by(Device.created_at.desc()).all()
    return jsonify([d.to_dict() for d in devices])


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
    return jsonify(device.to_dict()), 201


@devices_bp.route("/<int:device_id>", methods=["GET"])
def get_device(device_id):
    device = db.get_or_404(Device, device_id)
    return jsonify(device.to_dict())
