"""PathoHunt game blueprint — routes and API endpoints."""
import requests as _req
from flask import Blueprint, request, jsonify, render_template, Response
from flask_login import login_required, current_user

import services.game_service as game_service
from config.settings import KOKORO_URL

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


@bp.route("/game/pathohunt-3d/tutorial")
@login_required
def game_tutorial_3d():
    return render_template("game_tutorial_3d.html")


@bp.route("/game/pathohunt-3d/<target_id>")
@login_required
def game_battle_3d(target_id):
    boss = game_service.get_boss(target_id)
    if not boss:
        return render_template("game_lobby.html",
                               bosses=game_service.get_all_bosses(),
                               error="Unknown boss"), 404
    return render_template("game_battle_3d.html", boss=boss)


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


@bp.route("/game/pathohunt-3d")
@login_required
def game_selector_3d():
    bosses = game_service.get_all_bosses()
    return render_template("game_selector_3d.html", bosses=bosses)


@bp.route("/api/v3/game/session/<session_id>/candidates")
@login_required
def api_get_candidates(session_id):
    candidates = game_service.get_candidates(session_id, current_user.id)
    return jsonify({"candidates": candidates})


@bp.route("/api/v3/game/validate", methods=["POST"])
@login_required
def api_validate_novelty():
    data = request.get_json(silent=True) or {}
    smiles = (data.get("smiles") or "").strip()
    if not smiles:
        return jsonify({"error": "smiles required"}), 400
    return jsonify(game_service.validate_novelty(smiles))


# ─── Tutorial ─────────────────────────────────────────────────────────────────

@bp.route("/game/tutorial")
@login_required
def game_tutorial():
    return render_template("game_tutorial.html")


@bp.route("/api/v3/game/tts", methods=["POST"])
@login_required
def tts_proxy():
    """Proxy text to Kokoro TTS server and return WAV audio."""
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()[:800]
    voice = data.get("voice", "am_michael")
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        resp = _req.post(
            f"{KOKORO_URL}/generate-audio-binary/",
            json={"text": text, "voice_name": voice, "speed": 1.0},
            timeout=30,
        )
        resp.raise_for_status()
        return Response(resp.content, mimetype="audio/wav")
    except _req.exceptions.ConnectionError:
        return jsonify({"error": "Kokoro TTS service unreachable"}), 503
    except _req.exceptions.Timeout:
        return jsonify({"error": "Kokoro TTS timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500
