"""Evaluate Fine-tune — side-by-side comparison of production vs fine-tuned model."""
import statistics
from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user
from marshmallow import ValidationError

from api.schemas import CompareSchema
from services import molecule_generator, property_calculator, dti_predictor
from services.target_service import get_curated_target
from services.molecule_validator import validate_and_canonicalize
from utils.protein_utils import is_valid_sequence, clean_sequence

bp = Blueprint("evaluate_finetune", __name__)


@bp.route("/evaluate-finetune")
@login_required
def evaluate_page():
    target_id = request.args.get("target_id", "").strip()
    target = get_curated_target(target_id) if target_id else None
    return render_template("evaluate_finetune.html", target=target)


@bp.route("/api/v2/compare-models", methods=["POST"])
@login_required
def compare_models():
    try:
        data = CompareSchema().load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"error": e.messages}), 400

    aa_seq = clean_sequence(data["amino_acid_seq"])
    if aa_seq and not is_valid_sequence(aa_seq):
        return jsonify({"error": "Invalid amino acid sequence"}), 400

    canon_seed = validate_and_canonicalize(data["smile"])
    if canon_seed is None:
        return jsonify({"error": "Invalid seed SMILES"}), 400

    try:
        both = molecule_generator.generate_both(
            seed_smile=canon_seed,
            amino_acid_seq=aa_seq,
            noise=data["noise"],
            n=data["num_candidates"],
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    return jsonify({
        "production": _score_results(both["production"], canon_seed, aa_seq),
        "finetuned":  _score_results(both["finetuned"],  canon_seed, aa_seq),
        "comparison": _compare(
            _score_results(both["production"], canon_seed, aa_seq),
            _score_results(both["finetuned"],  canon_seed, aa_seq),
        ),
    }), 200


@bp.route("/api/v2/model-health")
@login_required
def model_health():
    return jsonify({
        "production":   molecule_generator.check_dgx_health(),
        "finetuned":    molecule_generator.check_finetuned_health(),
        "finetuned_v2": molecule_generator.check_finetuned_v2_health(),
    })


def _score_results(gen: dict, canon_seed: str, aa_seq: str) -> dict:
    if gen.get("error") and not gen["smiles"]:
        return {
            "candidates": [], "latency_ms": 0, "error": gen["error"],
            "stats": {"valid_count": 0, "avg_qed": 0, "avg_sas": 0,
                      "avg_composite": 0, "unique_rate": 0},
        }

    candidates = []
    for rank, smiles in enumerate(gen["smiles"], start=1):
        props = property_calculator.compute_all(smiles, canon_seed)
        if props is None:
            continue
        dti = dti_predictor.predict(props, aa_seq)
        comp = dti_predictor.composite_score(props, dti)
        candidates.append({
            "rank": rank,
            "smiles": smiles,
            "composite_score": round(comp, 3),
            "dti_score": round(dti, 3),
            **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in props.items()},
        })

    candidates.sort(key=lambda c: c["composite_score"], reverse=True)
    for i, c in enumerate(candidates, 1):
        c["rank"] = i

    n = len(candidates)
    stats = {
        "valid_count": n,
        "avg_qed": round(statistics.mean(c["qed"] for c in candidates), 3) if n else 0,
        "avg_sas": round(statistics.mean(c["sas"] for c in candidates), 3) if n else 0,
        "avg_composite": round(statistics.mean(c["composite_score"] for c in candidates), 3) if n else 0,
        "unique_rate": round(n / max(gen["total_generated"], 1), 3),
    }

    return {
        "candidates": candidates,
        "latency_ms": gen["latency_ms"],
        "total_parsed": gen["total_generated"],
        "stats": stats,
        "error": gen.get("error"),
    }


def _compare(prod: dict, ft: dict) -> dict:
    ps = prod["stats"]
    fs = ft["stats"]

    def winner(prod_val, ft_val, higher_better=True):
        if prod_val == ft_val:
            return "tie"
        if higher_better:
            return "production" if prod_val > ft_val else "finetuned"
        return "production" if prod_val < ft_val else "finetuned"

    validity_prod = ps["valid_count"] / max(prod.get("total_parsed", 1), 1)
    validity_ft   = fs["valid_count"] / max(ft.get("total_parsed", 1), 1)

    wins = {
        "validity":    winner(validity_prod, validity_ft),
        "avg_qed":     winner(ps["avg_qed"],     fs["avg_qed"]),
        "avg_sas":     winner(ps["avg_sas"],      fs["avg_sas"],      higher_better=False),
        "latency":     winner(prod["latency_ms"], ft["latency_ms"],   higher_better=False),
        "unique_rate": winner(ps["unique_rate"],  fs["unique_rate"]),
        "composite":   winner(ps["avg_composite"], fs["avg_composite"]),
    }

    weights = {"validity": 0.30, "avg_qed": 0.25, "avg_sas": 0.15,
               "composite": 0.15, "unique_rate": 0.10, "latency": 0.05}

    prod_score = sum(w for k, w in weights.items() if wins[k] == "production")
    ft_score   = sum(w for k, w in weights.items() if wins[k] == "finetuned")

    overall = "production" if prod_score > ft_score else ("finetuned" if ft_score > prod_score else "tie")

    return {
        "wins": wins,
        "overall_winner": overall,
        "production_score": round(prod_score, 2),
        "finetuned_score":  round(ft_score, 2),
        "validity_prod": round(validity_prod * 100, 1),
        "validity_ft":   round(validity_ft * 100, 1),
    }
