from flask import Blueprint, request, jsonify

from app import db, socketio
from app.models.device import Device
from app.models.test_result import TestResult

tests_bp = Blueprint("tests", __name__)


@tests_bp.route("/", methods=["POST"])
def submit_result():
    data = request.get_json()
    result = TestResult(
        device_id=data["device_id"],
        test_name=data["test_name"],
        passed=data["passed"],
        details=data.get("details"),
    )
    db.session.add(result)

    device = db.get_or_404(Device, data["device_id"])
    if not data["passed"]:
        device.status = "failed"
    db.session.commit()

    socketio.emit("test_result", result.to_dict())
    return jsonify(result.to_dict()), 201


@tests_bp.route("/device/<int:device_id>", methods=["GET"])
def device_results(device_id):
    results = TestResult.query.filter_by(device_id=device_id).all()
    return jsonify([r.to_dict() for r in results])
