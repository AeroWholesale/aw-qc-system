from datetime import datetime, timezone

from app import db


class Device(db.Model):
    __tablename__ = "devices"

    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(50), unique=True, nullable=False)
    device_type = db.Column(db.String(20), nullable=False)  # macbook, iphone, ipad
    model = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending, testing, passed, failed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    test_results = db.relationship("TestResult", backref="device", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "serial_number": self.serial_number,
            "device_type": self.device_type,
            "model": self.model,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
