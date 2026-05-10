"""PathoHunt game blueprint — routes and API endpoints."""
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user

import services.game_service as game_service

bp = Blueprint("game", __name__)


# ─── Page routes ─────────────────────────────────────────────────────────────

@bp.route("/game")
@login_required
def game_lobby():
    bosses = game_service.get_all_bosses()
    return render_template("game_lobby.html", bosses=bosses)


@bp.route("/game/battle/<target_id>")
@login_required
def game_battle(target_id):
    boss = game_service.get_boss(target_id)
    if not boss:
        return render_template("game_lobby.html",
                               bosses=game_service.get_all_bosses(),
                               error="Unknown boss"), 404
    return render_template("game_battle.html", boss=boss)


# ─── JSON API ─────────────────────────────────────────────────────────────────

@bp.route("/api/v3/game/bosses")
@login_required
def api_get_bosses():
    return jsonify(game_service.get_all_bosses())


@bp.route("/api/v3/game/session/start", methods=["POST"])
@login_required
def api_start_session():
    data = request.get_json(silent=True) or {}
    target_id = data.get("target_id")
    mode = data.get("mode", "quick_battle")
    difficulty = data.get("difficulty", "junior")

    if not target_id:
        return jsonify({"error": "target_id is required"}), 400
    if mode not in ("quick_battle", "docking_battle", "ai_army"):
        return jsonify({"error": "Invalid mode"}), 400
    if difficulty not in ("junior", "fellow", "pi", "nobel"):
        return jsonify({"error": "Invalid difficulty"}), 400

    try:
        session = game_service.start_session(current_user.id, target_id, mode, difficulty)
        boss = game_service.get_boss(target_id)
        return jsonify({"session": session.to_dict(), "boss": boss}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/v3/game/session/<session_id>")
@login_required
def api_get_session(session_id):
    state = game_service.get_session_state(session_id, current_user.id)
    if not state:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(state)


@bp.route("/api/v3/game/session/<session_id>/attack", methods=["POST"])
@login_required
def api_execute_attack(session_id):
    data = request.get_json(silent=True) or {}
    smiles = data.get("smiles", "").strip()

    try:
        result = game_service.execute_attack(session_id, smiles, current_user.id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"AI generation failed: {e}"}), 503
    except Exception as e:
        return jsonify({"error": f"Attack failed: {e}"}), 500


@bp.route("/api/v3/game/session/<session_id>/abandon", methods=["POST"])
@login_required
def api_abandon_session(session_id):
    ok = game_service.abandon_session(session_id, current_user.id)
    return jsonify({"ok": ok})


@bp.route("/api/v3/game/history")
@login_required
def api_game_history():
    history = game_service.get_history(current_user.id)
    return jsonify(history)
