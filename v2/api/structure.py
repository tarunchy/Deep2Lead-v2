"""Structure service API — fetch, fold, serve PDB files."""
import hashlib
import os
from flask import Blueprint, jsonify, request, Response
from flask_login import login_required, current_user

from services.structure_service import (
    fetch_rcsb_pdb, fetch_alphafold_pdb, fold_with_esmfold,
    get_best_structure, get_pdb_text_by_key
)
from services.target_service import get_curated_target
from services.xp_service import award_xp, award_badge
from config.settings import ESMFOLD_MAX_SEQ_LEN

bp = Blueprint("structure", __name__)


@bp.route("/api/v3/structure/pdb/<pdb_id>")
@login_required
def serve_rcsb(pdb_id):
    """Download and serve a PDB file by PDB ID."""
    pdb_text = fetch_rcsb_pdb(pdb_id)
    if not pdb_text:
        return jsonify({"error": f"PDB {pdb_id} not found"}), 404
    return Response(pdb_text, mimetype="text/plain",
                    headers={"Content-Disposition": f"inline; filename={pdb_id}.pdb"})


@bp.route("/api/v3/structure/alphafold/<uniprot_id>")
@login_required
def serve_alphafold(uniprot_id):
    """Fetch and serve AlphaFold predicted structure."""
    pdb_text, meta = fetch_alphafold_pdb(uniprot_id)
    if not pdb_text:
        return jsonify({"error": f"AlphaFold structure not available for {uniprot_id}"}), 404
    award_xp(current_user.id, "structure_viewed")
    award_badge(current_user.id, "structure_seeker")
    return Response(pdb_text, mimetype="text/plain",
                    headers={"Content-Disposition": f"inline; filename=AF-{uniprot_id}.pdb"})


@bp.route("/api/v3/structure/alphafold/<uniprot_id>/meta")
@login_required
def alphafold_meta(uniprot_id):
    """Return AlphaFold metadata only (fast)."""
    _, meta = fetch_alphafold_pdb(uniprot_id)
    if meta:
        return jsonify(meta)
    return jsonify({"error": "Not available"}), 404


@bp.route("/api/v3/structure/fold", methods=["POST"])
@login_required
def esmfold():
    """Fold a custom AA sequence using ESMFold API."""
    data = request.get_json()
    sequence = (data.get("sequence") or "").strip().upper()
    if not sequence:
        return jsonify({"error": "sequence required"}), 400
    if len(sequence) > ESMFOLD_MAX_SEQ_LEN:
        return jsonify({"error": f"Sequence too long. Maximum {ESMFOLD_MAX_SEQ_LEN} amino acids for real-time folding."}), 400

    pdb_text, err = fold_with_esmfold(sequence)
    if err:
        return jsonify({"error": err}), 500

    award_xp(current_user.id, "structure_viewed")
    award_badge(current_user.id, "structure_seeker")

    seq_hash = hashlib.sha256(sequence.encode()).hexdigest()[:16]
    return jsonify({
        "pdb_key": f"esm_{seq_hash}",
        "pdb_url": f"/api/v3/structure/cached/esm_{seq_hash}",
        "source": "esmfold",
        "source_label": "ESMFold (real-time AI prediction)",
        "warning": "ESMFold is fast but less accurate than AlphaFold2 for complex proteins. Blue regions = high confidence, red = low confidence.",
        "length": len(sequence),
    })


@bp.route("/api/v3/structure/cached/<key>")
@login_required
def serve_cached(key):
    """Serve any cached PDB by key (safe — key is a sanitized string)."""
    # Sanitize key to prevent path traversal
    safe_key = "".join(c for c in key if c.isalnum() or c in "_-")
    pdb_text = get_pdb_text_by_key(safe_key)
    if not pdb_text:
        return jsonify({"error": "Structure not found or not yet computed"}), 404
    return Response(pdb_text, mimetype="text/plain")


@bp.route("/api/v3/structure/best", methods=["POST"])
@login_required
def best_structure():
    """
    Given uniprot_id, pdb_id, and/or sequence, return the best available structure.
    Priority: experimental PDB > AlphaFold > ESMFold.
    """
    data = request.get_json()
    uniprot_id = data.get("uniprot_id")
    pdb_id = data.get("pdb_id")
    sequence = data.get("sequence")
    target_id = data.get("target_id")

    # If a curated target was selected, fill in missing IDs
    if target_id:
        t = get_curated_target(target_id)
        if t:
            uniprot_id = uniprot_id or t.get("uniprot_id")
            pdb_id = pdb_id or t.get("pdb_id")

    pdb_text, meta = get_best_structure(uniprot_id, pdb_id, sequence)
    if not pdb_text:
        return jsonify({"error": meta.get("error", "No structure available")}), 404

    # Determine cache key for serving
    if meta.get("source") == "rcsb" and pdb_id:
        cache_key = f"rcsb_{pdb_id.upper()}"
    elif meta.get("source") == "alphafold" and uniprot_id:
        cache_key = f"af_{uniprot_id.upper()}"
    elif meta.get("source") == "esmfold" and sequence:
        seq_hash = hashlib.sha256(sequence.encode()).hexdigest()[:16]
        cache_key = f"esm_{seq_hash}"
    else:
        cache_key = None

    award_xp(current_user.id, "structure_viewed")
    award_badge(current_user.id, "structure_seeker")

    return jsonify({
        "source": meta.get("source"),
        "source_label": meta.get("source_label"),
        "pdb_url": f"/api/v3/structure/cached/{cache_key}" if cache_key else None,
        "warning": meta.get("warning"),
        "meta": {k: v for k, v in meta.items() if k not in ("source", "source_label", "warning")},
    })
