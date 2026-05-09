from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user

from models.db_models import db, Experiment, Comment, Like
from api.schemas import CommentSchema
from marshmallow import ValidationError
from services.molecule_generator import check_dgx_health

bp = Blueprint("feed", __name__)


@bp.route("/feed")
@login_required
def feed_page():
    return render_template("feed.html")


@bp.route("/api/health")
def health():
    dgx_ok = check_dgx_health()
    return jsonify({
        "status": "ok",
        "dgx_gemma4": "ready" if dgx_ok else "unavailable",
    })


@bp.route("/api/v2/feed")
@login_required
def get_feed():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 12, type=int)
    sort = request.args.get("sort", "newest")  # newest | likes | comments
    cohort = request.args.get("cohort")

    query = Experiment.query.filter_by(status="published")
    if cohort:
        from models.db_models import User
        query = query.join(User).filter(User.cohort == cohort)

    if sort == "newest":
        query = query.order_by(Experiment.published_at.desc())
    else:
        query = query.order_by(Experiment.published_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = [e.to_dict() for e in pagination.items]

    if sort == "likes":
        items.sort(key=lambda x: x["like_count"], reverse=True)
    elif sort == "comments":
        items.sort(key=lambda x: x["comment_count"], reverse=True)

    # Annotate with current user's like status
    liked_ids = {
        str(l.experiment_id)
        for l in Like.query.filter_by(user_id=current_user.id).all()
    }
    for item in items:
        item["liked_by_me"] = item["id"] in liked_ids

    return jsonify({
        "items": items,
        "total": pagination.total,
        "pages": pagination.pages,
        "page": page,
    })


# ── Likes ────────────────────────────────────────────────────────────

@bp.route("/api/v2/experiments/<experiment_id>/like", methods=["POST"])
@login_required
def toggle_like(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    if exp.status != "published":
        return jsonify({"error": "Experiment is not published"}), 400

    existing = Like.query.filter_by(
        user_id=current_user.id, experiment_id=exp.id
    ).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(Like(user_id=current_user.id, experiment_id=exp.id))
        liked = True
    db.session.commit()
    return jsonify({"liked": liked, "like_count": exp.like_count})


# ── Comments ─────────────────────────────────────────────────────────

@bp.route("/api/v2/experiments/<experiment_id>/comments", methods=["GET", "POST"])
@login_required
def comments(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)

    if request.method == "GET":
        top_level = (
            Comment.query
            .filter_by(experiment_id=exp.id, parent_id=None)
            .order_by(Comment.created_at.asc())
            .all()
        )
        return jsonify([c.to_dict(include_replies=True) for c in top_level])

    # POST
    try:
        data = CommentSchema().load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"error": e.messages}), 400

    comment = Comment(
        experiment_id=exp.id,
        user_id=current_user.id,
        body=data["body"],
        tag=data.get("tag"),
        parent_id=data.get("parent_id"),
    )
    db.session.add(comment)
    db.session.commit()
    return jsonify(comment.to_dict()), 201


@bp.route("/api/v2/comments/<comment_id>", methods=["DELETE", "PATCH"])
@login_required
def comment_action(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    is_owner = str(comment.user_id) == str(current_user.id)
    is_admin = current_user.role == "admin"

    if request.method == "DELETE":
        if not (is_owner or is_admin):
            return jsonify({"error": "Forbidden"}), 403
        comment.is_deleted = True
        db.session.commit()
        return jsonify({"status": "deleted"})

    # PATCH — edit own comment
    if not is_owner:
        return jsonify({"error": "Forbidden"}), 403
    body = (request.get_json() or {}).get("body", "").strip()
    if not body:
        return jsonify({"error": "Body required"}), 400
    comment.body = body
    comment.is_edited = True
    comment.edited_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(comment.to_dict())
