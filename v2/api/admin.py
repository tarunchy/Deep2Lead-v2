from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from marshmallow import ValidationError
from models.db_models import db, User, Experiment
from api.schemas import CreateUserSchema, UpdateUserSchema

bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated


@bp.route("/admin")
@admin_required
def overview():
    stats = {
        "total_users": User.query.count(),
        "active_students": User.query.filter_by(role="student", is_active=True).count(),
        "total_experiments": Experiment.query.count(),
        "published": Experiment.query.filter_by(status="published").count(),
    }
    return render_template("admin/overview.html", stats=stats)


@bp.route("/admin/users")
@admin_required
def users_page():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)


@bp.route("/api/admin/users", methods=["POST"])
@admin_required
def create_user():
    try:
        data = CreateUserSchema().load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"error": e.messages}), 400
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username already exists"}), 409
    user = User(
        username=data["username"],
        display_name=data.get("display_name") or data["username"],
        email=data.get("email"),
        role=data.get("role", "student"),
        cohort=data.get("cohort"),
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@bp.route("/api/admin/users/<user_id>", methods=["PATCH"])
@admin_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    try:
        data = UpdateUserSchema().load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"error": e.messages}), 400
    for key, val in data.items():
        setattr(user, key, val)
    db.session.commit()
    return jsonify(user.to_dict())
