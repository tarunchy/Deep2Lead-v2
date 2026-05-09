import requests as http
from flask import Blueprint, render_template, request, Response, jsonify
from flask_login import login_required
from config.settings import DGX_TIMEOUT

KOKORO_URL = "http://dlyog05:5151"

bp = Blueprint("tutorial", __name__)


@bp.route("/tutorial")
@login_required
def tutorial_page():
    return render_template("tutorial.html")


@bp.route("/api/v2/tts", methods=["POST"])
@login_required
def tts_proxy():
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400
    voice = data.get("voice", "af_heart")
    speed = float(data.get("speed", 0.92))
    try:
        resp = http.post(
            f"{KOKORO_URL}/generate-audio-binary/",
            json={"text": text, "voice": voice, "speed": speed},
            timeout=DGX_TIMEOUT,
        )
        resp.raise_for_status()
        return Response(resp.content, mimetype="audio/wav")
    except Exception as e:
        return jsonify({"error": f"TTS unavailable: {e}"}), 503
