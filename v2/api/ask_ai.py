"""Ask AI — voice/text Q&A: Whisper STT proxy + dedicated page."""
import requests as _req
from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from config.settings import WHISPER_URL, WHISPER_TIMEOUT

bp = Blueprint("ask_ai", __name__)


@bp.route("/ask-ai")
@login_required
def ask_ai_page():
    return render_template("ask_ai.html")


@bp.route("/api/v2/stt", methods=["POST"])
@login_required
def speech_to_text():
    """Proxy audio blob to Whisper service on dlyog05, return transcript."""
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "No audio file provided"}), 400

    try:
        resp = _req.post(
            WHISPER_URL,
            files={"audio": (audio.filename or "recording.webm",
                             audio.stream,
                             audio.content_type or "audio/webm")},
            timeout=WHISPER_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return jsonify({"transcript": data["transcription"]})
        return jsonify({"error": data.get("error", "Transcription failed")}), 500
    except _req.exceptions.ConnectionError:
        return jsonify({"error": "Whisper service unreachable (dlyog05:5002)"}), 503
    except _req.exceptions.Timeout:
        return jsonify({"error": "Whisper transcription timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500
