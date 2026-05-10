from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, Response
from flask_login import login_required, current_user
from marshmallow import ValidationError
import requests as http

from models.db_models import db, Experiment, Candidate
from api.schemas import GenerateSchema, ExperimentUpdateSchema
from services import molecule_generator, property_calculator, dti_predictor
from services.molecule_validator import validate_and_canonicalize
from utils.mol_utils import mol_to_svg
from utils.protein_utils import is_valid_sequence, clean_sequence
from config.settings import DGX_BASE_URL, DGX_TIMEOUT

bp = Blueprint("experiments", __name__)


# ── Page routes ────────────────────────────────────────────────────

@bp.route("/")
@login_required
def index():
    return redirect(url_for("feed.feed_page"))


@bp.route("/dashboard")
@login_required
def dashboard():
    drafts = (
        Experiment.query.filter_by(user_id=current_user.id, status="draft")
        .order_by(Experiment.created_at.desc()).all()
    )
    published = (
        Experiment.query.filter_by(user_id=current_user.id, status="published")
        .order_by(Experiment.published_at.desc()).all()
    )
    return render_template("dashboard.html", drafts=drafts, published=published)


@bp.route("/run")
@login_required
def run_page():
    return render_template("run.html")


@bp.route("/experiments/<experiment_id>")
@login_required
def experiment_detail(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    if exp.status != "published" and str(exp.user_id) != str(current_user.id) and current_user.role != "admin":
        return jsonify({"error": "Not found"}), 404
    return render_template("experiment.html", experiment=exp)


# ── API: molecule SVG ───────────────────────────────────────────────

@bp.route("/api/v2/mol/svg")
@login_required
def mol_svg():
    smiles = request.args.get("smiles", "")
    svg = mol_to_svg(smiles)
    if svg is None:
        return "Invalid SMILES", 400
    return Response(svg, mimetype="image/svg+xml")


# ── API: validate / properties ─────────────────────────────────────

@bp.route("/api/v2/validate", methods=["POST"])
@login_required
def validate_smiles():
    data = request.get_json() or {}
    canon = validate_and_canonicalize(data.get("smiles", ""))
    return jsonify({"valid": canon is not None, "canonical": canon})


@bp.route("/api/v2/properties", methods=["POST"])
@login_required
def get_properties():
    data = request.get_json() or {}
    smiles = data.get("smiles", "")
    seed = data.get("seed_smile", smiles)
    props = property_calculator.compute_all(smiles, seed)
    if props is None:
        return jsonify({"error": "Invalid SMILES"}), 400
    return jsonify(props)


# ── API: generate experiment ────────────────────────────────────────

@bp.route("/api/v2/generate", methods=["POST"])
@login_required
def generate():
    try:
        data = GenerateSchema().load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"error": e.messages}), 400

    aa_seq = clean_sequence(data["amino_acid_seq"])
    if aa_seq and not is_valid_sequence(aa_seq):
        return jsonify({"error": "Invalid amino acid sequence"}), 400

    canon_seed = validate_and_canonicalize(data["smile"])
    if canon_seed is None:
        return jsonify({"error": "Invalid seed SMILES"}), 400

    try:
        gen = molecule_generator.generate(
            seed_smile=canon_seed,
            amino_acid_seq=aa_seq,
            noise=data["noise"],
            n=data["num_candidates"],
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    exp = Experiment(
        user_id=current_user.id,
        amino_acid_seq=aa_seq,
        seed_smile=canon_seed,
        noise_level=data["noise"],
        num_requested=data["num_candidates"],
        gemma4_latency_ms=gen["latency_ms"],
        num_valid_generated=gen["total_generated"],
        target_id=data.get("target_id") or None,
        pdb_id=data.get("pdb_id") or None,
        mode=data.get("mode", "2d"),
    )
    db.session.add(exp)
    db.session.flush()  # get exp.id before commit

    seed_props = property_calculator.compute_all(canon_seed, canon_seed)
    candidates = []
    for rank, smiles in enumerate(gen["smiles"], start=1):
        props = property_calculator.compute_all(smiles, canon_seed)
        if props is None:
            continue
        dti = dti_predictor.predict(props, aa_seq)
        comp = dti_predictor.composite_score(props, dti)
        c = Candidate(
            experiment_id=exp.id,
            smiles=smiles,
            rank=rank,
            dti_score=dti,
            composite_score=comp,
            **props,
        )
        candidates.append(c)

    # Re-rank by composite score
    candidates.sort(key=lambda c: c.composite_score, reverse=True)
    for i, c in enumerate(candidates, start=1):
        c.rank = i
        db.session.add(c)

    db.session.commit()

    return jsonify({
        "experiment_id": str(exp.id),
        "seed_properties": seed_props,
        "candidates": [c.to_dict() for c in candidates],
        "meta": {
            "generated": gen["total_generated"],
            "returned": len(candidates),
            "gemma4_latency_ms": gen["latency_ms"],
        },
    }), 201


# ── API: experiment CRUD ────────────────────────────────────────────

@bp.route("/api/v2/experiments")
@login_required
def list_experiments():
    q = Experiment.query.filter_by(user_id=current_user.id)
    mode_filter = request.args.get("mode")
    if mode_filter:
        q = q.filter_by(mode=mode_filter)
    exps = q.order_by(Experiment.created_at.desc()).all()
    return jsonify({"experiments": [e.to_dict() for e in exps]})


@bp.route("/api/v2/experiments/<experiment_id>", methods=["GET", "PATCH"])
@login_required
def experiment(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    if request.method == "GET":
        if exp.status != "published" and str(exp.user_id) != str(current_user.id) and current_user.role != "admin":
            return jsonify({"error": "Not found"}), 404
        return jsonify(exp.to_dict(include_candidates=True))

    # PATCH
    if str(exp.user_id) != str(current_user.id) and current_user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403
    try:
        data = ExperimentUpdateSchema().load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"error": e.messages}), 400
    for key, val in data.items():
        setattr(exp, key, val)
    db.session.commit()
    return jsonify(exp.to_dict())


@bp.route("/api/v2/experiments/<experiment_id>/publish", methods=["POST"])
@login_required
def publish(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    if str(exp.user_id) != str(current_user.id):
        return jsonify({"error": "Forbidden"}), 403
    if not exp.title:
        return jsonify({"error": "Add a title before publishing"}), 400
    exp.status = "published"
    exp.published_at = datetime.now(timezone.utc)
    exp.version += 1
    db.session.commit()
    return jsonify({"status": "published"})


@bp.route("/api/v2/experiments/<experiment_id>/retract", methods=["POST"])
@login_required
def retract(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    if str(exp.user_id) != str(current_user.id) and current_user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403
    exp.status = "retracted"
    db.session.commit()
    return jsonify({"status": "retracted"})


# ── API: AI metadata suggestion ─────────────────────────────────────

@bp.route("/api/v2/suggest-metadata", methods=["POST"])
@login_required
def suggest_metadata():
    data = request.get_json() or {}
    experiment_id = data.get("experiment_id")
    if not experiment_id:
        return jsonify({"error": "experiment_id required"}), 400

    exp = Experiment.query.get_or_404(experiment_id)
    if str(exp.user_id) != str(current_user.id):
        return jsonify({"error": "Forbidden"}), 403

    top_candidates = sorted(exp.candidates, key=lambda c: c.composite_score, reverse=True)[:3]
    candidate_lines = "\n".join(
        f"  {i+1}. SMILES={c.smiles} | Score={c.composite_score:.3f} | DTI={c.dti_score:.3f} | QED={c.qed:.3f} | SAS={c.sas:.2f}"
        for i, c in enumerate(top_candidates)
    ) or "  No valid candidates generated."

    prompt = f"""You are a computational chemistry assistant helping a graduate student document their drug discovery experiment.

Experiment details:
- Seed SMILES: {exp.seed_smile}
- Protein target (first 80 residues): {exp.amino_acid_seq[:80]}
- Diversity level: {exp.noise_level:.2f} (0=close analogs, 1=diverse)
- Candidates generated: {exp.num_valid_generated}

Top candidates by composite score:
{candidate_lines}

Write a concise experiment title (max 12 words) and a 2-3 sentence scientific hypothesis explaining what structural modifications were explored and why they may improve drug-target binding.

Respond in this exact JSON format (no markdown, no extra text):
{{"title": "...", "hypothesis": "..."}}"""

    try:
        resp = http.post(
            f"{DGX_BASE_URL}/v1/text",
            json={"prompt": prompt, "max_new_tokens": 200, "temperature": 0.7},
            timeout=DGX_TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")
    except Exception as e:
        return jsonify({"error": f"Gemma4 unavailable: {e}"}), 503

    import json as _json, re
    match = re.search(r'\{.*?"title".*?"hypothesis".*?\}', raw, re.DOTALL)
    if not match:
        return jsonify({"error": "Could not parse Gemma4 response", "raw": raw[:300]}), 502
    try:
        suggestion = _json.loads(match.group())
    except _json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON from Gemma4", "raw": raw[:300]}), 502

    return jsonify({
        "title": suggestion.get("title", "").strip(),
        "hypothesis": suggestion.get("hypothesis", "").strip(),
    })
