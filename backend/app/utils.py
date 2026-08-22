import os
import uuid
from functools import wraps
from flask import current_app
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from werkzeug.utils import secure_filename
from .models import User

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_complaint_photo(file):
    if not file or file.filename == "":
        return None
    if not allowed_file(file.filename):
        raise ValueError("Invalid image file format")
    
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_filename)
    file.save(filepath)
    return unique_filename

def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            if not user or user.role != "admin":
                return {"error": "Admin access required"}, 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper
