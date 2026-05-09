from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, Response
from flask_login import login_required, current_user
from marshmallow import ValidationError

from models.db_models import db, Experiment, Candidate
from api.schemas import GenerateSchema, ExperimentUpdateSchema
from services import molecule_generator, property_calculator, dti_predictor
from services.molecule_validator import validate_and_canonicalize
from utils.mol_utils import mol_to_svg
from utils.protein_utils import is_valid_sequence, clean_sequence

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
    if not is_valid_sequence(aa_seq):
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
    exps = (
        Experiment.query.filter_by(user_id=current_user.id)
        .order_by(Experiment.created_at.desc()).all()
    )
    return jsonify([e.to_dict() for e in exps])


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
