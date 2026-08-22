from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="resident") # "resident" or "admin"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    complaints = db.relationship("Complaint", backref="resident", lazy=True, foreign_keys="Complaint.resident_id")
    notices = db.relationship("Notice", backref="admin", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat()
        }


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    resident_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category = db.Column(db.String(50), nullable=False) # e.g., Plumbing, Electrical, Lift
    description = db.Column(db.Text, nullable=False)
    photo_filename = db.Column(db.String(255), nullable=True)
    priority = db.Column(db.String(20), default="Medium") # Low, Medium, High
    status = db.Column(db.String(20), default="Open") # Open, In Progress, Resolved
    is_overdue = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 1-to-many relationship for tracking status lifecycle history
    history = db.relationship("ComplaintHistory", backref="complaint", cascade="all, delete-orphan", order_by="ComplaintHistory.timestamp.asc()")

    def to_dict(self):
        return {
            "id": self.id,
            "resident_id": self.resident_id,
            "resident_name": self.resident.name if self.resident else "Unknown",
            "category": self.category,
            "description": self.description,
            "photo_url": f"/api/uploads/{self.photo_filename}" if self.photo_filename else None,
            "priority": self.priority,
            "status": self.status,
            "is_overdue": self.is_overdue,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "history": [h.to_dict() for h in self.history]
        }


class ComplaintHistory(db.Model):
    __tablename__ = "complaint_history"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    note = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    actor = db.relationship("User", foreign_keys=[actor_id])

    def to_dict(self):
        return {
            "id": self.id,
            "complaint_id": self.complaint_id,
            "status": self.status,
            "actor_id": self.actor_id,
            "actor_name": self.actor.name if self.actor else "System",
            "actor_role": self.actor.role if self.actor else "System",
            "note": self.note,
            "timestamp": self.timestamp.isoformat()
        }


class Notice(db.Model):
    __tablename__ = "notices"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_important = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "admin_id": self.admin_id,
            "admin_name": self.admin.name if self.admin else "Admin",
            "title": self.title,
            "content": self.content,
            "is_important": self.is_important,
            "created_at": self.created_at.isoformat()
        }
