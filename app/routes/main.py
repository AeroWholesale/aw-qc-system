from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@main_bp.route("/station")
def station():
    return render_template("station.html")


@main_bp.route("/device/<int:device_id>")
def device_detail(device_id):
    return render_template("device_detail.html", device_id=device_id)


@main_bp.route("/health")
def health():
    return {"status": "ok"}
