"""Docking API — run AutoDock Vina jobs, retrieve results."""
import os
import threading
import uuid as _uuid
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from services.docking_service import run_docking_pipeline, is_docking_available
from services.structure_service import get_best_structure, get_cached_pdb_path, fetch_rcsb_pdb
from services.target_service import get_curated_target
from services.xp_service import award_xp, award_badge
from models import db, DockingResult, ProteinStructure, Candidate
from config.settings import DOCKING_EXHAUSTIVENESS

bp = Blueprint("docking", __name__)

# In-memory job tracker for async docking
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


@bp.route("/api/v3/docking/available")
@login_required
def docking_available():
    return jsonify({"available": is_docking_available()})


@bp.route("/api/v3/docking/run", methods=["POST"])
@login_required
def run_docking():
    """
    Start a docking job.
    Body: { smiles, target_id OR pdb_id/uniprot_id, candidate_id (optional) }
    Returns: { job_id } — poll /api/v3/docking/job/<job_id> for result.
    """
    data = request.get_json()
    smiles = data.get("smiles", "").strip()
    target_id = data.get("target_id")
    pdb_id = data.get("pdb_id")
    uniprot_id = data.get("uniprot_id")
    candidate_id = data.get("candidate_id")
    sequence = data.get("sequence")

    if not smiles:
        return jsonify({"error": "smiles required"}), 400
    if not is_docking_available():
        return jsonify({"error": "Docking not available on this server (Vina not installed).", "available": False}), 503

    # Resolve target info
    binding_center = [0.0, 0.0, 0.0]
    binding_size = [25, 25, 25]
    if target_id:
        t = get_curated_target(target_id)
        if t:
            pdb_id = pdb_id or t.get("pdb_id")
            uniprot_id = uniprot_id or t.get("uniprot_id")
            binding_center = t.get("binding_site_center", binding_center)
            binding_size = t.get("binding_site_size", binding_size)

    # Ensure we have a cached PDB file
    pdb_path = None
    if pdb_id:
        fetch_rcsb_pdb(pdb_id)  # populates cache
        pdb_path = get_cached_pdb_path(pdb_id)
    if not pdb_path and uniprot_id:
        from services.structure_service import fetch_alphafold_pdb, STRUCTURE_CACHE_DIR
        from config.settings import STRUCTURE_CACHE_DIR as _SD
        _, meta = fetch_alphafold_pdb(uniprot_id)
        if meta:
            candidate_key = f"af_{uniprot_id.upper()}"
            pdb_path = os.path.join(_SD, f"{candidate_key}.pdb")
            if not os.path.exists(pdb_path):
                pdb_path = None

    if not pdb_path:
        return jsonify({"error": "No protein structure available for docking. Fetch the structure first."}), 400

    job_id = str(_uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"status": "pending", "result": None, "error": None}

    def _do_dock():
        result = run_docking_pipeline(
            smiles=smiles,
            pdb_file_path=pdb_path,
            binding_site_center=binding_center,
            binding_site_size=binding_size,
            exhaustiveness=DOCKING_EXHAUSTIVENESS,
        )
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "done" if not result.get("error") else "failed",
                "result": result,
                "error": result.get("error"),
            }

    threading.Thread(target=_do_dock, daemon=True).start()
    return jsonify({"job_id": job_id, "status": "pending"})


@bp.route("/api/v3/docking/job/<job_id>")
@login_required
def docking_job_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job["status"] == "done":
        result = job["result"]
        award_xp(current_user.id, "first_dock")
        award_badge(current_user.id, "docking_rookie")
        return jsonify({
            "status": "done",
            "docking_score_kcal": result.get("docking_score_kcal"),
            "docking_score_norm": result.get("docking_score_norm"),
            "interpretation": _interpret_score(result.get("docking_score_kcal")),
        })
    return jsonify({"status": job["status"], "error": job.get("error")})


def _interpret_score(kcal: float | None) -> dict:
    """Plain-English explanation of a docking score."""
    if kcal is None:
        return {"label": "Unknown", "color": "gray", "text": "No docking score available."}
    if kcal <= -10:
        return {"label": "Excellent", "color": "green",
                "text": f"Score of {kcal:.1f} kcal/mol — very strong simulated binding. This molecule fits the binding pocket exceptionally well in the model."}
    if kcal <= -8:
        return {"label": "Strong", "color": "blue",
                "text": f"Score of {kcal:.1f} kcal/mol — strong simulated binding, comparable to many approved drugs."}
    if kcal <= -6:
        return {"label": "Moderate", "color": "yellow",
                "text": f"Score of {kcal:.1f} kcal/mol — moderate binding. Promising but would need optimization."}
    if kcal <= -4:
        return {"label": "Weak", "color": "orange",
                "text": f"Score of {kcal:.1f} kcal/mol — weak simulated binding. The molecule may not fit the pocket well."}
    return {"label": "Poor", "color": "red",
            "text": f"Score of {kcal:.1f} kcal/mol — very weak or no binding detected in simulation."}
