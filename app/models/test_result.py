from datetime import datetime, timezone

from app import db


class TestResult(db.Model):
    __tablename__ = "test_results"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=False)
    test_name = db.Column(db.String(100), nullable=False)
    test_category = db.Column(db.String(50))
    passed = db.Column(db.Boolean, nullable=False)
    skipped = db.Column(db.Boolean, default=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "test_name": self.test_name,
            "test_category": self.test_category,
            "passed": self.passed,
            "skipped": self.skipped,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
        }
