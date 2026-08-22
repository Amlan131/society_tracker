from datetime import datetime
import os
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from . import db
from .models import User, Complaint, ComplaintHistory, Notice
from .utils import save_complaint_photo, admin_required
from .tasks import send_email_async

api = Blueprint("api", __name__)

# --- Static File Serving ---
@api.route("/uploads/<filename>", methods=["GET"])
def get_uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

# --- Authentication ---
@api.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    if not all(k in data for k in ("name", "email", "password")):
        return jsonify({"error": "Missing required fields"}), 400

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409

    role = data.get("role", "resident")
    user = User(name=data["name"], email=data["email"], role=role)
    user.set_password(data["password"])

    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 201


@api.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    user = User.query.filter_by(email=data.get("email")).first()

    if not user or not user.check_password(data.get("password", "")):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 200

# --- Resident Complaints ---
@api.route("/complaints", methods=["POST"])
@jwt_required()
def create_complaint():
    user_id = int(get_jwt_identity())
    category = request.form.get("category")
    description = request.form.get("description")
    photo = request.files.get("photo")

    if not category or not description:
        return jsonify({"error": "Category and description are required"}), 400

    photo_filename = None
    if photo:
        try:
            photo_filename = save_complaint_photo(photo)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    complaint = Complaint(
        resident_id=user_id,
        category=category,
        description=description,
        photo_filename=photo_filename,
        status="Open",
        priority="Medium"
    )
    db.session.add(complaint)
    db.session.flush()

    # Initial history log
    initial_history = ComplaintHistory(
        complaint_id=complaint.id,
        status="Open",
        actor_id=user_id,
        note="Complaint raised by resident."
    )
    db.session.add(initial_history)
    db.session.commit()

    return jsonify(complaint.to_dict()), 201


@api.route("/complaints/me", methods=["GET"])
@jwt_required()
def get_my_complaints():
    user_id = int(get_jwt_identity())
    complaints = Complaint.query.filter_by(resident_id=user_id).order_by(Complaint.created_at.desc()).all()
    return jsonify([c.to_dict() for c in complaints]), 200

# --- Admin Complaints & Lifecycle Management ---
@api.route("/admin/complaints", methods=["GET"])
@admin_required()
def get_all_complaints():
    category = request.args.get("category")
    status = request.args.get("status")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = Complaint.query

    if category:
        query = query.filter(Complaint.category == category)
    if status:
        query = query.filter(Complaint.status == status)
    if start_date:
        query = query.filter(Complaint.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Complaint.created_at <= datetime.fromisoformat(end_date))

    # Overdue complaints surfaced at the top, followed by newest
    complaints = query.order_by(Complaint.is_overdue.desc(), Complaint.created_at.desc()).all()
    return jsonify([c.to_dict() for c in complaints]), 200


@api.route("/admin/complaints/<int:complaint_id>", methods=["PUT"])
@admin_required()
def update_complaint_status(complaint_id):
    admin_id = int(get_jwt_identity())
    data = request.get_json() or {}
    complaint = Complaint.query.get_or_404(complaint_id)

    new_status = data.get("status")
    new_priority = data.get("priority")
    note = data.get("note", "")

    status_changed = False
    if new_priority and new_priority in ["Low", "Medium", "High"]:
        complaint.priority = new_priority

    if new_status and new_status in ["Open", "In Progress", "Resolved"] and new_status != complaint.status:
        complaint.status = new_status
        status_changed = True

        # If resolved, it's no longer considered actively overdue
        if new_status == "Resolved":
            complaint.is_overdue = False

        # Record Status Lifecycle History
        history = ComplaintHistory(
            complaint_id=complaint.id,
            status=new_status,
            actor_id=admin_id,
            note=note
        )
        db.session.add(history)

        # Trigger Async Email Notification to Resident
        resident = complaint.resident
        if resident and resident.email:
            email_body = f"Hello {resident.name},\n\nYour complaint (#{complaint.id} - {complaint.category}) status has been updated to '{new_status}'.\nNote: {note}\n\nThank you,\nSociety Management"
            send_email_async.delay(resident.email, f"Complaint #{complaint.id} Status Updated", email_body)

    db.session.commit()
    return jsonify(complaint.to_dict()), 200

# --- Admin Dashboard & Metrics ---
@api.route("/admin/dashboard", methods=["GET"])
@admin_required()
def get_dashboard_metrics():
    total_open = Complaint.query.filter_by(status="Open").count()
    total_in_progress = Complaint.query.filter_by(status="In Progress").count()
    total_resolved = Complaint.query.filter_by(status="Resolved").count()
    total_overdue = Complaint.query.filter_by(is_overdue=True).count()

    # Group counts by category
    categories = db.session.query(Complaint.category, db.func.count(Complaint.id)).group_by(Complaint.category).all()
    by_category = {cat: count for cat, count in categories}

    return jsonify({
        "status_metrics": {
            "Open": total_open,
            "In Progress": total_in_progress,
            "Resolved": total_resolved
        },
        "overdue_count": total_overdue,
        "by_category": by_category
    }), 200

# --- Notices ---
@api.route("/notices", methods=["GET"])
@jwt_required()
def get_notices():
    # Important (pinned) notices first, then newest
    notices = Notice.query.order_by(Notice.is_important.desc(), Notice.created_at.desc()).all()
    return jsonify([n.to_dict() for n in notices]), 200


@api.route("/notices", methods=["POST"])
@admin_required()
def create_notice():
    admin_id = int(get_jwt_identity())
    data = request.get_json() or {}
    
    title = data.get("title")
    content = data.get("content")
    is_important = data.get("is_important", False)

    if not title or not content:
        return jsonify({"error": "Title and content are required"}), 400

    notice = Notice(admin_id=admin_id, title=title, content=content, is_important=is_important)
    db.session.add(notice)
    db.session.commit()

    # Trigger Async Email to all residents if marked important
    if is_important:
        residents = User.query.filter_by(role="resident").all()
        for r in residents:
            body = f"Important Notice: {title}\n\n{content}\n\nRegards,\nSociety Management"
            send_email_async.delay(r.email, f"Important Notice: {title}", body)

    return jsonify(notice.to_dict()), 201
