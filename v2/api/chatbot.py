"""Gemma-powered chatbot with server-side tool use (novelty, properties, validation)."""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
import requests as http

from models.db_models import Experiment
from config.settings import DGX_BASE_URL, DGX_TIMEOUT
from api.chatbot_tools import extract_smiles, detect_intents, run_tools

bp = Blueprint("chatbot", __name__)

SYSTEM = """You are a helpful AI assistant embedded in Deep2Lead, a drug discovery platform for students.
Help users explore experiments, understand molecular properties, and learn drug discovery.

Platform facts:
- Molecules use SMILES notation (e.g. CC(=O)Oc1ccccc1C(=O)O is Aspirin)
- QED 0-1 (drug-likeness, higher=better), SAS 1-10 (synthesizability, lower=easier)
- LogP ideal 0-3 (oral bioavailability), MW ideal <500 Da, Tanimoto 0-1 (seed similarity)
- Composite score = 35% DTI + 30% QED + 20% inverse-SAS + 15% Tanimoto
- Lipinski rule of 5: MW<500, LogP<5, H-donors<5, H-acceptors<10

Be concise. Show SMILES in backticks. Reference tool results as facts — do not speculate beyond them."""


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

    # ── Tool use: extract SMILES, detect intent, run tools ───────────
    smiles_found = extract_smiles(message)
    tool_output = ""
    tool_names_used = []
    if smiles_found:
        smiles = smiles_found[0]
        intents = detect_intents(message, smiles_found)
        tool_output = run_tools(smiles, intents)
        tool_names_used = intents

    # ── Build prompt ─────────────────────────────────────────────────
    context = _build_context(current_user.id)
    username = current_user.display_name or current_user.username

    hist_str = ""
    for h in history[-6:]:
        role = "User" if h.get("role") == "user" else "Assistant"
        hist_str += f"\n{role}: {h.get('content', '')}"

    tools_section = ""
    if tool_output:
        tools_section = f"\n\n--- TOOL RESULTS (real data, use these facts in your answer) ---\n{tool_output}\n---"

    prompt = (
        f"{SYSTEM}\n\n"
        f"Current user: {username}\n"
        f"User experiments:\n{context}"
        f"{tools_section}"
        f"{hist_str}\n"
        f"User: {message}\n"
        f"Assistant:"
    )

    try:
        resp = http.post(
            f"{DGX_BASE_URL}/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.7,
            },
            timeout=DGX_TIMEOUT,
        )
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"].strip()
        if not reply:
            return jsonify({"error": "Empty response from Gemma4"}), 502
        return jsonify({"reply": reply, "tools_used": tool_names_used})
    except Exception as e:
        return jsonify({"error": f"Gemma4 unavailable: {e}"}), 503
