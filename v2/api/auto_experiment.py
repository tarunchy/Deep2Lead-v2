"""Auto Experiment API — start/stop loop, SSE progress stream, results."""
import json
import time
import uuid as _uuid
from flask import Blueprint, jsonify, request, render_template, Response, stream_with_context
from flask_login import login_required, current_user

from services.auto_exp_runner import start_auto_experiment, stop_auto_experiment, get_run_state
from services.xp_service import award_xp, award_badge
from models import db, AutoExperimentRun, Experiment
from config.settings import AUTO_EXP_MAX_ROUNDS, AUTO_EXP_MAX_MOLECULES

bp = Blueprint("auto_experiment", __name__)


@bp.route("/auto-experiment")
@login_required
def auto_exp_page():
    return render_template("auto_experiment.html")


@bp.route("/api/v3/auto-experiment/start", methods=["POST"])
@login_required
def start():
    data = request.get_json()
    experiment_id = data.get("experiment_id")
    rounds = min(int(data.get("rounds", 3)), AUTO_EXP_MAX_ROUNDS)
    molecules_per_round = min(int(data.get("molecules_per_round", 5)), AUTO_EXP_MAX_MOLECULES)

    exp = Experiment.query.filter_by(id=experiment_id, user_id=current_user.id).first()
    if not exp:
        return jsonify({"error": "Experiment not found or not yours"}), 404

    # Detect mode: evolve if top candidate exists, rescue if 0 candidates
    top_candidate = exp.candidates.first()
    if top_candidate:
        mode = "evolve"
        seed_smiles = top_candidate.smiles
        strategy = data.get("strategy", "balanced")
    else:
        mode = "rescue"
        seed_smiles = exp.seed_smile
        strategy = "auto"  # runner will cycle through all strategies

    # Get structure + target info
    from services.structure_service import get_cached_pdb_path
    from services.target_service import get_curated_target
    structure_path = None
    binding_center = [0, 0, 0]
    target_info = {}
    if exp.pdb_id:
        structure_path = get_cached_pdb_path(exp.pdb_id)
    if exp.target_id:
        t = get_curated_target(exp.target_id)
        if t:
            binding_center = t.get("binding_site_center", [0, 0, 0])
            target_info = {
                "name": t.get("name", ""),
                "disease": t.get("disease", ""),
                "category": t.get("category", ""),
            }

    run = AutoExperimentRun(
        experiment_id=exp.id,
        strategy=strategy,
        rounds_planned=rounds,
        molecules_per_round=molecules_per_round,
        status="running",
    )
    db.session.add(run)
    db.session.commit()
    run_id = str(run.id)

    config = {
        "experiment_id": str(exp.id),
        "seed_smiles": seed_smiles,
        "amino_acid_seq": exp.amino_acid_seq or "",
        "mode": mode,
        "strategy": strategy,
        "rounds": rounds,
        "molecules_per_round": molecules_per_round,
        "structure_path": structure_path,
        "binding_site_center": binding_center,
        "target_info": target_info,
    }

    from flask import current_app
    start_auto_experiment(run_id, config, current_app._get_current_object())

    return jsonify({"run_id": run_id, "status": "running", "mode": mode, "target_info": target_info})


@bp.route("/api/v3/auto-experiment/<run_id>/stop", methods=["POST"])
@login_required
def stop(run_id):
    stop_auto_experiment(run_id)
    run = AutoExperimentRun.query.get(_uuid.UUID(run_id))
    if run:
        run.status = "stopped"
        db.session.commit()
    return jsonify({"status": "stopped"})


@bp.route("/api/v3/auto-experiment/<run_id>/status")
@login_required
def status(run_id):
    state = get_run_state(run_id)
    if state:
        return jsonify(state)
    # Fall back to DB record
    run = AutoExperimentRun.query.get(_uuid.UUID(run_id))
    if run:
        return jsonify(run.to_dict(include_rounds=True))
    return jsonify({"error": "Run not found"}), 404


@bp.route("/api/v3/auto-experiment/<run_id>/stream")
@login_required
def stream(run_id):
    """Server-Sent Events stream for live round-by-round updates."""
    def generate():
        last_log_len = 0
        last_round_len = 0
        timeout = 600  # 10 min max
        start = time.time()

        while time.time() - start < timeout:
            state = get_run_state(run_id)
            if not state:
                yield f"data: {json.dumps({'error': 'run not found'})}\n\n"
                break

            # Send new log lines
            logs = state.get("logs", [])
            if len(logs) > last_log_len:
                for line in logs[last_log_len:]:
                    yield f"data: {json.dumps({'type': 'log', 'message': line})}\n\n"
                last_log_len = len(logs)

            # Send new rounds
            rounds = state.get("rounds", [])
            if len(rounds) > last_round_len:
                for r in rounds[last_round_len:]:
                    yield f"data: {json.dumps({'type': 'round', 'round': r})}\n\n"
                last_round_len = len(rounds)

            # Send state update
            yield f"data: {json.dumps({'type': 'state', 'status': state.get('status'), 'best_score': state.get('best_score'), 'rounds_completed': state.get('rounds_completed', 0)})}\n\n"

            if state.get("status") in ("complete", "stopped", "failed"):
                # Award XP/badge on completion
                if state.get("status") == "complete":
                    award_xp(current_user.id, "auto_exp_complete")
                    award_badge(current_user.id, "loop_master")
                yield f"data: {json.dumps({'type': 'done', 'status': state.get('status')})}\n\n"
                break

            time.sleep(2)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@bp.route("/api/v3/auto-experiment/<run_id>/report")
@login_required
def report(run_id):
    run = AutoExperimentRun.query.get(_uuid.UUID(run_id))
    if not run:
        return jsonify({"error": "Run not found"}), 404
    return jsonify(run.to_dict(include_rounds=True))
