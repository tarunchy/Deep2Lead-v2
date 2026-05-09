"""Target discovery API — curated library, UniProt search, RCSB lookup."""
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required

from services.target_service import (
    get_curated_targets, get_curated_target,
    full_target_search, search_rcsb, check_alphafold
)

bp = Blueprint("target", __name__)


@bp.route("/run-3d")
@login_required
def run_3d_page():
    target_id = request.args.get("target_id", "").strip()
    target = get_curated_target(target_id) if target_id else None
    return render_template("run_3d.html", target=target)


@bp.route("/target-picker")
@login_required
def target_picker_page():
    return render_template("target_picker.html")


@bp.route("/api/v3/targets/curated")
@login_required
def curated_list():
    targets = get_curated_targets()
    # Group by category
    grouped = {}
    for t in targets:
        cat = t["category"]
        grouped.setdefault(cat, []).append(t)
    return jsonify({"targets": targets, "grouped": grouped, "total": len(targets)})


@bp.route("/api/v3/targets/<target_id>")
@login_required
def curated_detail(target_id):
    t = get_curated_target(target_id)
    if not t:
        return jsonify({"error": "Target not found"}), 404
    # Optionally enrich with RCSB structures
    structures = search_rcsb(t["uniprot_id"], max_results=3)
    af = check_alphafold(t["uniprot_id"])
    return jsonify({
        "target": t,
        "experimental_structures": structures,
        "alphafold": af,
    })


@bp.route("/api/v3/targets/search")
@login_required
def search_targets():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"error": "Query too short"}), 400
    results = full_target_search(q)
    return jsonify(results)


@bp.route("/api/v3/targets/<uniprot_id>/structures")
@login_required
def get_structures(uniprot_id):
    structures = search_rcsb(uniprot_id)
    af = check_alphafold(uniprot_id)
    return jsonify({"experimental": structures, "alphafold": af})
