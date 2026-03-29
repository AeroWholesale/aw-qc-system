from datetime import datetime, timezone

from app import db


class Device(db.Model):
    __tablename__ = "devices"

    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(50), unique=True, nullable=False)
    device_type = db.Column(db.String(20), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default="pending")
    station_id = db.Column(db.String(50))
    tested_by = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)

    test_results = db.relationship("TestResult", backref="device", lazy=True)

    def finalize(self):
        has_fail = any(not r.passed for r in self.test_results if not r.skipped)
        self.status = "failed" if has_fail else "passed"
        self.completed_at = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            "id": self.id,
            "serial_number": self.serial_number,
            "device_type": self.device_type,
            "model": self.model,
            "status": self.status,
            "station_id": self.station_id,
            "tested_by": self.tested_by,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "pass_count": sum(1 for r in self.test_results if r.passed and not r.skipped),
            "fail_count": sum(1 for r in self.test_results if not r.passed and not r.skipped),
            "total_tests": len(self.test_results),
        }
