from flask import Blueprint, request, jsonify

from app import db, socketio
from app.models.device import Device
from app.models.test_result import TestResult
from app.models.test_definition import TestDefinition

tests_bp = Blueprint("tests", __name__)


@tests_bp.route("/definitions/<device_type>", methods=["GET"])
def get_definitions(device_type):
    defs = TestDefinition.query.filter_by(
        device_type=device_type, is_active=True
    ).order_by(TestDefinition.display_order).all()
    return jsonify([d.to_dict() for d in defs])


@tests_bp.route("/", methods=["POST"])
def submit_result():
    data = request.get_json()
    result = TestResult(
        device_id=data["device_id"],
        test_name=data["test_name"],
        test_category=data.get("test_category"),
        passed=data["passed"],
        skipped=data.get("skipped", False),
        details=data.get("details"),
    )
    db.session.add(result)
    db.session.commit()
    socketio.emit("test_result", result.to_dict())
    return jsonify(result.to_dict()), 201


@tests_bp.route("/batch", methods=["POST"])
def submit_batch():
    data = request.get_json()
    device_id = data["device_id"]
    device = db.get_or_404(Device, device_id)

    results = []
    for item in data["results"]:
        result = TestResult(
            device_id=device_id,
            test_name=item["test_name"],
            test_category=item.get("test_category"),
            passed=item["passed"],
            skipped=item.get("skipped", False),
            details=item.get("details"),
        )
        db.session.add(result)
        results.append(result)

    device.finalize()
    db.session.commit()

    socketio.emit("device_complete", device.to_dict(), room="dashboard")
    return jsonify({
        "device": device.to_dict(),
        "results": [r.to_dict() for r in results],
    })


@tests_bp.route("/device/<int:device_id>", methods=["GET"])
def device_results(device_id):
    results = TestResult.query.filter_by(device_id=device_id).all()
    return jsonify([r.to_dict() for r in results])
