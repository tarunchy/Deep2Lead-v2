"""Gamification API — XP, badges, missions."""
from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user

from services.xp_service import (
    get_user_xp, get_user_badges, get_missions, seed_badges, BADGE_DEFINITIONS
)

bp = Blueprint("gamification", __name__)


@bp.route("/missions")
@login_required
def mission_board():
    return render_template("mission_board.html")


@bp.route("/api/v3/me/xp")
@login_required
def my_xp():
    return jsonify(get_user_xp(current_user.id))


@bp.route("/api/v3/me/badges")
@login_required
def my_badges():
    earned = get_user_badges(current_user.id)
    earned_slugs = {b["badge_slug"] for b in earned}
    all_badges = [
        {**bd, "earned": bd["slug"] in earned_slugs}
        for bd in BADGE_DEFINITIONS
    ]
    return jsonify({"earned": earned, "all": all_badges})


@bp.route("/api/v3/me/missions")
@login_required
def my_missions():
    missions = get_missions(current_user.id)
    return jsonify({"missions": missions})


@bp.route("/api/v3/badges/all")
@login_required
def all_badges():
    return jsonify({"badges": BADGE_DEFINITIONS})
