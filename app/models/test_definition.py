from app import db


class TestDefinition(db.Model):
    __tablename__ = "test_definitions"

    id = db.Column(db.Integer, primary_key=True)
    test_name = db.Column(db.String(100), nullable=False)
    test_category = db.Column(db.String(50), nullable=False)
    device_type = db.Column(db.String(20), nullable=False)
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    instructions = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "test_name": self.test_name,
            "test_category": self.test_category,
            "device_type": self.device_type,
            "display_order": self.display_order,
            "instructions": self.instructions,
        }
