"""PathoHunt game blueprint — routes and API endpoints."""
import requests as _req
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, render_template, Response
from flask_login import login_required, current_user

import services.game_service as game_service
import services.lab_service as lab_service
from models.game_progression import CoopSession, LabUpgrade
from models.db_models import db
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


@bp.route("/game/lab")
@login_required
def game_lab():
    return render_template("game_lab.html")


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
    unlocked = game_service.get_unlocked_level_numbers(current_user.id)
    for boss in bosses:
        boss["unlocked"] = boss.get("game_level", 99) in unlocked
    return render_template("game_selector_3d.html", bosses=bosses)


@bp.route("/game/history")
@login_required
def game_history():
    return render_template("game_history.html")


@bp.route("/api/v3/game/history/full")
@login_required
def api_game_history_full():
    history = game_service.get_history(current_user.id)
    return jsonify(history)


@bp.route("/api/v3/game/session/<session_id>/save", methods=["POST"])
@login_required
def api_save_session_to_experiment(session_id):
    try:
        result = game_service.save_session_to_experiment(session_id, current_user.id)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Save failed: {e}"}), 500


@bp.route("/api/v3/game/session/<session_id>/candidates")
@login_required
def api_get_candidates(session_id):
    pinned_seed = request.args.get("pinned_seed", "").strip() or None
    candidates = game_service.get_candidates(session_id, current_user.id, pinned_seed=pinned_seed)
    return jsonify({"candidates": candidates})


@bp.route("/api/v3/game/design-molecule", methods=["POST"])
@login_required
def api_design_molecule():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()[:600]
    blocks = data.get("blocks") or []
    target_id = data.get("target_id", "")
    if not prompt and not blocks:
        return jsonify({"error": "prompt or blocks required"}), 400
    try:
        result = game_service.design_molecule(prompt=prompt, blocks=blocks, target_id=target_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/v3/game/validate", methods=["POST"])
@login_required
def api_validate_novelty():
    data = request.get_json(silent=True) or {}
    smiles = (data.get("smiles") or "").strip()
    if not smiles:
        return jsonify({"error": "smiles required"}), 400
    return jsonify(game_service.validate_novelty(smiles))


# ─── Leaderboard ─────────────────────────────────────────────────────────────

@bp.route("/api/v3/game/leaderboard/<target_id>")
@login_required
def api_get_leaderboard(target_id):
    entries = game_service.get_leaderboard(target_id)
    return jsonify(entries)


# ─── Research Points ──────────────────────────────────────────────────────────

@bp.route("/api/v3/game/rp")
@login_required
def api_get_rp():
    rp = game_service.get_user_rp(current_user.id)
    return jsonify({"rp": rp})


# ─── Lab Upgrades ─────────────────────────────────────────────────────────────

@bp.route("/api/v3/game/upgrades")
@login_required
def api_get_upgrades():
    all_upgrades = LabUpgrade.query.all()
    owned_slugs = {u["upgrade_slug"] for u in lab_service.get_user_upgrades(current_user.id)}
    result = []
    for up in all_upgrades:
        d = up.to_dict()
        d["owned"] = up.slug in owned_slugs
        result.append(d)
    return jsonify(result)


@bp.route("/api/v3/game/upgrade/purchase", methods=["POST"])
@login_required
def api_purchase_upgrade():
    data = request.get_json(silent=True) or {}
    slug = (data.get("slug") or "").strip()
    if not slug:
        return jsonify({"error": "slug is required"}), 400
    try:
        result = lab_service.purchase_upgrade(current_user.id, slug)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Purchase failed: {e}"}), 500


# ─── Co-op Analyst ────────────────────────────────────────────────────────────

@bp.route("/api/v3/game/session/<session_id>/analyst")
@login_required
def api_analyst_view(session_id):
    return render_template("game_analyst.html", session_id=session_id)


@bp.route("/api/v3/game/session/<session_id>/join-analyst", methods=["POST"])
@login_required
def api_join_analyst(session_id):
    existing = CoopSession.query.filter_by(session_id=session_id).first()
    if existing:
        existing.analyst_user_id = current_user.id
        existing.joined_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify(existing.to_dict())

    coop = CoopSession(
        session_id=session_id,
        analyst_user_id=current_user.id,
        joined_at=datetime.now(timezone.utc),
        analyst_annotations={},
    )
    db.session.add(coop)
    db.session.commit()
    return jsonify(coop.to_dict()), 201


@bp.route("/api/v3/game/session/<session_id>/annotate", methods=["POST"])
@login_required
def api_annotate_session(session_id):
    data = request.get_json(silent=True) or {}
    coop = CoopSession.query.filter_by(session_id=session_id).first()
    if not coop:
        return jsonify({"error": "No co-op session found"}), 404
    if str(coop.analyst_user_id) != str(current_user.id):
        return jsonify({"error": "Not the analyst for this session"}), 403
    annotations = coop.analyst_annotations or {}
    annotations.update(data)
    coop.analyst_annotations = annotations
    db.session.commit()
    return jsonify(coop.to_dict())


# ─── Tutorial ─────────────────────────────────────────────────────────────────

@bp.route("/game/tutorial")
@login_required
def game_tutorial():
    return render_template("game_tutorial.html")


@bp.route("/api/v3/game/tts", methods=["POST"])
@login_required
def tts_proxy():
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
