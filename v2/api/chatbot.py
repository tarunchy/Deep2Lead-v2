"""Gemma-powered chatbot for natural language exploration of the app."""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
import requests as http

from models.db_models import Experiment
from config.settings import DGX_BASE_URL, DGX_TIMEOUT

bp = Blueprint("chatbot", __name__)

SYSTEM = """You are a helpful AI assistant embedded in Deep2Lead, a drug discovery platform for students.
Help users explore their experiments, understand molecular properties, and learn drug discovery concepts.

Platform facts:
- Molecules are described using SMILES notation (e.g. CC(=O)Oc1ccccc1C(=O)O is Aspirin)
- Properties: QED 0-1 (drug-likeness, higher=better), SAS 1-10 (synthesizability, lower=easier),
  LogP (lipophilicity, ideal 0-3), MW in Daltons (ideal <500), Tanimoto 0-1 (similarity to seed)
- Composite score = 35% DTI + 30% QED + 20% inverse-SAS + 15% Tanimoto
- Lipinski rule of 5: MW<500, LogP<5, H-donors<5, H-acceptors<10
- Gemma4 AI runs on NVIDIA DGX hardware to generate candidates in seconds

Be concise. Show SMILES strings in backticks. Answer directly without restating the question."""


def _build_context(user_id) -> str:
    exps = (Experiment.query
            .filter_by(user_id=user_id)
            .order_by(Experiment.created_at.desc())
            .limit(5)
            .all())
    if not exps:
        return "User has no experiments yet."
    lines = []
    for exp in exps:
        top = sorted(exp.candidates, key=lambda c: c.composite_score or 0, reverse=True)[:1]
        top_str = ""
        if top:
            c = top[0]
            top_str = (f", top candidate: `{c.smiles}` "
                       f"(score:{c.composite_score:.2f} QED:{c.qed:.2f} SAS:{c.sas:.1f} "
                       f"MW:{c.mw:.0f} Lipinski:{'pass' if c.lipinski_pass else 'fail'})")
        lines.append(
            f'- "{exp.title or "Untitled"}" [{exp.status}] seed:`{exp.seed_smile}`{top_str}'
        )
    return "\n".join(lines)


@bp.route("/api/v2/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return jsonify({"error": "Empty message"}), 400

    context = _build_context(current_user.id)
    username = current_user.display_name or current_user.username

    hist_str = ""
    for h in history[-6:]:
        role = "User" if h.get("role") == "user" else "Assistant"
        hist_str += f"\n{role}: {h.get('content', '')}"

    prompt = f"""{SYSTEM}

Current user: {username}
User's experiments:
{context}
{hist_str}
User: {message}
Assistant:"""

    try:
        resp = http.post(
            f"{DGX_BASE_URL}/v1/text",
            json={"prompt": prompt, "max_tokens": 400, "temperature": 0.7},
            timeout=DGX_TIMEOUT,
        )
        resp.raise_for_status()
        reply = resp.json().get("response", "").strip()
        if not reply:
            return jsonify({"error": "Empty response from Gemma4"}), 502
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": f"Gemma4 unavailable: {e}"}), 503
