/* ask_ai.js — Voice + text Q&A: Whisper STT → LLM → Kokoro TTS */
(function () {
  "use strict";

  // States: idle | recording | transcribing | thinking | speaking
  let _state    = "idle";
  let _recorder = null;
  let _chunks   = [];
  let _history  = [];          // [{role, content}] for LLM context
  let _playingAudio = null;    // current TTS audio element

  // ── DOM refs ──────────────────────────────────────────────────
  const feed     = () => document.getElementById("askFeed");
  const textarea = () => document.getElementById("askInput");
  const micBtn   = () => document.getElementById("askMic");
  const sendBtn  = () => document.getElementById("askSend");
  const status   = () => document.getElementById("askStatus");

  // ── Init ──────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    sendBtn().addEventListener("click", _handleSend);
    micBtn().addEventListener("click",  _toggleMic);

    textarea().addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); _handleSend(); }
    });

    // Auto-resize textarea
    textarea().addEventListener("input", () => {
      const el = textarea();
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 120) + "px";
    });
  });

  // ── Hint chips ────────────────────────────────────────────────
  window.askHint = function (text) {
    textarea().value = text;
    textarea().dispatchEvent(new Event("input"));
    textarea().focus();
  };

  // ── Send ──────────────────────────────────────────────────────
  function _handleSend() {
    const text = textarea().value.trim();
    if (!text || _state === "thinking" || _state === "speaking") return;
    textarea().value = "";
    textarea().style.height = "auto";
    _ask(text);
  }

  // ── Mic toggle ────────────────────────────────────────────────
  async function _toggleMic() {
    if (_state === "recording") {
      _stopRecording();
    } else if (_state === "idle") {
      await _startRecording();
    }
  }

  async function _startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      _chunks = [];
      _recorder = new MediaRecorder(stream, { mimeType: _bestMime() });
      _recorder.ondataavailable = e => e.data.size > 0 && _chunks.push(e.data);
      _recorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        _transcribe(new Blob(_chunks, { type: _recorder.mimeType }));
      };
      _recorder.start();
      _setState("recording");
    } catch (e) {
      _setStatus("Microphone access denied — please allow mic in browser settings.", "");
    }
  }

  function _stopRecording() {
    if (_recorder && _recorder.state !== "inactive") _recorder.stop();
    _setState("transcribing");
  }

  function _bestMime() {
    const types = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg", "audio/mp4"];
    return types.find(t => MediaRecorder.isTypeSupported(t)) || "";
  }

  // ── Whisper STT ───────────────────────────────────────────────
  async function _transcribe(blob) {
    _setStatus("🎙 Transcribing…", "thinking");
    try {
      const form = new FormData();
      form.append("audio", blob, "recording.webm");
      const res  = await fetch("/api/v2/stt", { method: "POST", body: form });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      const text = data.transcript.trim();
      if (!text) { _setState("idle"); _setStatus("No speech detected — try again.", ""); return; }
      _setState("idle");
      textarea().value = text;
      textarea().dispatchEvent(new Event("input"));
      _ask(text);
    } catch (e) {
      _setState("idle");
      _setStatus("Transcription failed: " + e.message, "");
    }
  }

  // ── LLM call ──────────────────────────────────────────────────
  async function _ask(text) {
    _appendUserMsg(text);
    _history.push({ role: "user", content: text });
    if (_history.length > 16) _history = _history.slice(-16);

    _setState("thinking");
    const typingEl = _appendTyping();

    try {
      const res  = await fetch("/api/v2/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: _history.slice(0, -1) }),
      });
      const data = await res.json();
      const reply = data.reply || data.error || "Sorry, I couldn't understand that.";

      typingEl.remove();
      _history.push({ role: "assistant", content: reply });

      const msgEl = _appendAiMsg(reply, data.tools_used || []);
      _setState("idle");

      // Auto-play TTS
      await _speak(reply, msgEl);

    } catch (e) {
      typingEl.remove();
      _appendAiMsg("Sorry, there was an error reaching the AI. Please try again.", []);
      _setState("idle");
    }
  }

  // ── Kokoro TTS ────────────────────────────────────────────────
  async function _speak(text, msgEl) {
    const btn = msgEl?.querySelector(".ai-play-btn");
    _setState("speaking");
    _setPlayBtn(btn, true);

    try {
      const res  = await fetch("/api/v2/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: "af_heart", speed: 0.92 }),
      });
      if (!res.ok) throw new Error("TTS failed");
      const url = URL.createObjectURL(await res.blob());
      const audio = new Audio(url);
      _playingAudio = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        _playingAudio = null;
        _setState("idle");
        _setPlayBtn(btn, false);
      };
      audio.onerror = () => { _setState("idle"); _setPlayBtn(btn, false); };
      await audio.play();
    } catch {
      _setState("idle");
      _setPlayBtn(btn, false);
    }
  }

  // Called when user manually clicks ▶/⏸ on an AI message
  window.toggleSpeech = async function (btn, text) {
    if (_playingAudio) {
      _playingAudio.pause();
      _playingAudio = null;
      _setState("idle");
      btn.textContent = "▶ Play";
      btn.classList.remove("playing");
      return;
    }
    const msgEl = btn.closest(".ai-msg");
    await _speak(text, msgEl);
  };

  // ── DOM helpers ───────────────────────────────────────────────
  function _appendUserMsg(text) {
    const el = document.createElement("div");
    el.className = "ai-msg user";
    el.innerHTML = `
      <div class="ai-avatar">👤</div>
      <div class="ai-bubble">${_esc(text)}</div>`;
    feed().appendChild(el);
    _scrollFeed();
  }

  function _appendTyping() {
    const el = document.createElement("div");
    el.className = "ai-msg ai";
    el.id = "typingIndicator";
    el.innerHTML = `
      <div class="ai-avatar">🤖</div>
      <div class="ai-bubble">
        <div class="ai-typing"><span></span><span></span><span></span></div>
      </div>`;
    feed().appendChild(el);
    _scrollFeed();
    return el;
  }

  function _appendAiMsg(text, toolsUsed) {
    const safeText = _esc(text).replace(/`([^`]+)`/g, "<code>$1</code>");
    const tools = (toolsUsed || []).map(t => {
      const labels = { novelty: "🔍 Novelty", properties: "⚗️ Properties", validate: "✓ SMILES" };
      return `<span class="hint-chip" style="cursor:default;">${labels[t] || t}</span>`;
    }).join("");

    const rawText = text; // for TTS onclick
    const el = document.createElement("div");
    el.className = "ai-msg ai";
    el.innerHTML = `
      <div class="ai-avatar">🤖</div>
      <div class="ai-bubble">
        <div>${safeText}</div>
        ${tools ? `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;">${tools}</div>` : ""}
        <button class="ai-play-btn" onclick="toggleSpeech(this, ${JSON.stringify(rawText)})">▶ Play</button>
      </div>`;
    feed().appendChild(el);
    _scrollFeed();
    return el;
  }

  function _setPlayBtn(btn, playing) {
    if (!btn) return;
    btn.textContent = playing ? "⏸ Pause" : "▶ Play";
    btn.classList.toggle("playing", playing);
  }

  function _scrollFeed() {
    const f = feed();
    if (f) f.scrollTop = f.scrollHeight;
  }

  function _esc(s) {
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
            .replace(/"/g,"&quot;").replace(/\n/g,"<br>");
  }

  // ── State machine ─────────────────────────────────────────────
  function _setState(s) {
    _state = s;
    const mic  = micBtn();
    const send = sendBtn();
    const txt  = textarea();

    const messages = {
      idle:         "",
      recording:    '<span class="status-dot-live"></span> Recording… click mic to stop',
      transcribing: "🎙 Transcribing your question…",
      thinking:     "🤖 Thinking…",
      speaking:     "🔊 Speaking…",
    };

    _setStatus(messages[s] || "", s);

    if (mic) {
      mic.classList.toggle("recording", s === "recording");
      mic.textContent = s === "recording" ? "⏹" : "🎙";
      mic.disabled = s === "transcribing" || s === "thinking" || s === "speaking";
    }
    if (send) send.disabled = s === "thinking" || s === "speaking";
    if (txt)  txt.disabled  = s === "transcribing" || s === "thinking";
  }

  function _setStatus(msg, cls) {
    const el = status();
    if (!el) return;
    el.innerHTML = msg;
    el.className = "askai-status " + (cls || "");
  }
})();
