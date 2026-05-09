/* ask_ai.js — Voice globe + text chatbot Q&A */
(function () {
  "use strict";

  let _state        = "idle";
  let _recorder     = null;
  let _chunks       = [];
  let _history      = [];
  let _playingAudio = null;
  let _stopPlayback = false;

  // ── DOM refs ──────────────────────────────────────────────────
  const voOverlay = () => document.getElementById("voiceOverlay");
  const voLabel   = () => document.getElementById("voLabel");
  const voStatus  = () => document.getElementById("askStatus");
  const micGlobe  = () => document.getElementById("askMic");

  const txOverlay = () => document.getElementById("textOverlay");
  const feed      = () => document.getElementById("askFeed");
  const textarea  = () => document.getElementById("askInput");
  const micText   = () => document.getElementById("askMicText");
  const sendBtn   = () => document.getElementById("askSend");
  const txStatus  = () => document.getElementById("askStatusText");

  // ── Mode switch ───────────────────────────────────────────────
  window.askSetMode = function (mode) {
    if (mode === "text") {
      voOverlay()?.style.setProperty("display", "none");
      txOverlay()?.classList.add("active");
    } else {
      txOverlay()?.classList.remove("active");
      voOverlay()?.style.removeProperty("display");
      // resize globe after it's visible again
      setTimeout(() => { if (window.GlobeViz) GlobeViz.resize(); }, 60);
    }
  };

  // ── Init ──────────────────────────────────────────────────────
  const _GREETINGS = [
    "Hey! I'm your AI research assistant — what's on your mind today?",
    "Hi there! How can I help you with drug discovery today?",
    "Hello! I'm ready to help. What would you like to explore?",
    "Hey! What's on your mind? I'm here to help.",
  ];

  async function _greetUser() {
    const msg = _GREETINGS[Math.floor(Math.random() * _GREETINGS.length)];
    const lbl = voLabel();
    if (lbl) lbl.textContent = "Hello!";
    _setState("speaking");
    const audio = await _fetchTtsAudio(msg);
    if (audio) await _playAudioObj(audio);
    _setState("idle");
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (window.GlobeViz) GlobeViz.load("globeCanvas", () => setTimeout(_greetUser, 900));

    micGlobe()?.addEventListener("click", _toggleMic);
    micText()?.addEventListener("click",  _toggleMic);
    sendBtn()?.addEventListener("click",  _handleSend);

    textarea()?.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); _handleSend(); }
    });
    textarea()?.addEventListener("input", () => {
      const el = textarea();
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 120) + "px";
    });
  });

  // ── Hint chips ────────────────────────────────────────────────
  window.askHint = function (text) {
    askSetMode("text");
    setTimeout(() => {
      const el = textarea();
      if (!el) return;
      el.value = text;
      el.dispatchEvent(new Event("input"));
      el.focus();
    }, 60);
  };

  // ── Send ──────────────────────────────────────────────────────
  function _handleSend() {
    const text = textarea()?.value.trim();
    if (!text || _state === "thinking" || _state === "speaking") return;
    textarea().value = "";
    textarea().style.height = "auto";
    _ask(text);
  }

  // ── Mic ───────────────────────────────────────────────────────
  async function _toggleMic() {
    if (_state === "recording") _stopRecording();
    else if (_state === "idle") await _startRecording();
  }

  async function _startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      _chunks = [];

      // ── VAD: auto-stop after 2s of silence post-speech ──────────
      let _audioCtx = null, _silenceTimer = null, _hasSpeech = false, _vadIv = null;
      try {
        _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const src  = _audioCtx.createMediaStreamSource(stream);
        const anal = _audioCtx.createAnalyser();
        anal.fftSize = 512;
        src.connect(anal);
        const buf = new Uint8Array(anal.frequencyBinCount);
        const THRESH = 14, HOLD = 2000;
        _vadIv = setInterval(() => {
          if (_state !== "recording") { clearInterval(_vadIv); return; }
          anal.getByteFrequencyData(buf);
          const avg = buf.reduce((s, v) => s + v, 0) / buf.length;
          if (avg > THRESH) {
            _hasSpeech = true;
            clearTimeout(_silenceTimer); _silenceTimer = null;
          } else if (_hasSpeech && !_silenceTimer) {
            _silenceTimer = setTimeout(() => {
              if (_state === "recording") _stopRecording();
            }, HOLD);
          }
        }, 120);
      } catch { /* VAD unavailable — manual stop only */ }

      _recorder = new MediaRecorder(stream, { mimeType: _bestMime() });
      _recorder.ondataavailable = e => e.data.size > 0 && _chunks.push(e.data);
      _recorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        clearInterval(_vadIv);
        clearTimeout(_silenceTimer);
        _audioCtx?.close().catch(() => {});
        _transcribe(new Blob(_chunks, { type: _recorder.mimeType }));
      };
      _recorder.start();
      _setState("recording");
    } catch {
      _setVoStatus("Microphone access denied.", "");
    }
  }

  function _stopRecording() {
    if (_recorder && _recorder.state !== "inactive") _recorder.stop();
    _setState("transcribing");
  }

  function _bestMime() {
    const t = ["audio/webm;codecs=opus","audio/webm","audio/ogg","audio/mp4"];
    return t.find(m => MediaRecorder.isTypeSupported(m)) || "";
  }

  // ── STT ───────────────────────────────────────────────────────
  async function _transcribe(blob) {
    _setState("transcribing");
    try {
      const form = new FormData();
      form.append("audio", blob, "recording.webm");
      const res  = await fetch("/api/v2/stt", { method: "POST", body: form });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      const text = data.transcript?.trim();
      if (!text) { _setState("idle"); return; }
      _setState("idle");
      // Stay in current mode (globe stays visible if in voice mode)
      _ask(text);
    } catch (e) {
      _setState("idle");
      _setVoStatus("Transcription failed: " + e.message, "");
    }
  }

  // ── Acknowledgment ────────────────────────────────────────────
  const _ACKS = [
    "Sure! Let me think about that and I'll answer in just a moment.",
    "Great question! Give me a second to research that for you.",
    "Absolutely, let me look into that and get back to you shortly.",
    "Good question! I'm working on your answer right now.",
    "Of course! Let me think through that — I'll have an answer in just a second.",
    "Sure thing! Let me dig into that question for you.",
  ];
  const _randomAck = () => _ACKS[Math.floor(Math.random() * _ACKS.length)];

  // ── Text cleanup + chunking ───────────────────────────────────
  function _cleanText(t) {
    return t
      .replace(/```[\s\S]*?```/g, "")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\*\*(.+?)\*\*/g, "$1")
      .replace(/\*(.+?)\*/g, "$1")
      .replace(/^#{1,6}\s+/gm, "")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/^[-*+]\s+/gm, "")
      .replace(/^\d+\.\s+/gm, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function _chunkText(text, maxLen = 400) {
    const result = [];
    // Split at every newline so colon-terminated intro lines ("involves:") get their own chunk
    for (const line of text.split(/\n+/)) {
      const p = line.trim();
      if (!p) continue;
      if (p.length <= maxLen) {
        result.push(p);
      } else {
        // Long paragraph: split at sentence boundaries
        const sents = p.match(/[^.!?]+[.!?]+\s*/g) || [p];
        let cur = "";
        for (const s of sents) {
          if (cur && (cur + s).length > maxLen) { result.push(cur.trim()); cur = s; }
          else cur += s;
        }
        if (cur.trim()) result.push(cur.trim());
      }
    }
    return result.length ? result : [text];
  }

  // ── LLM call ──────────────────────────────────────────────────
  async function _ask(text) {
    _appendUserMsg(text);
    _history.push({ role: "user", content: text });
    if (_history.length > 16) _history = _history.slice(-16);

    _setState("thinking");
    const typingEl = _appendTyping();

    const llmPromise = fetch("/api/v2/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: _history.slice(0, -1) }),
    });
    const ackAudio = await _fetchTtsAudio(_randomAck());
    if (ackAudio) await _playAudioObj(ackAudio);

    try {
      const res   = await llmPromise;
      const data  = await res.json();
      const reply = data.reply || data.error || "Sorry, I couldn't understand that.";

      typingEl.remove();
      _history.push({ role: "assistant", content: reply });
      const msgEl = _appendAiMsg(reply, data.tools_used || []);
      _setState("idle");
      await _speakChunked(reply, msgEl);
    } catch {
      typingEl.remove();
      _appendAiMsg("Sorry, there was an error reaching the AI. Please try again.", []);
      _setState("idle");
    }
  }

  // ── TTS ───────────────────────────────────────────────────────
  async function _fetchTtsAudio(text) {
    try {
      const res = await fetch("/api/v2/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: "af_heart", speed: 0.92 }),
      });
      if (!res.ok) return null;
      const url = URL.createObjectURL(await res.blob());
      const a = new Audio(url);
      a._blobUrl = url;
      return a;
    } catch { return null; }
  }

  function _playAudioObj(audio) {
    return new Promise(resolve => {
      _playingAudio = audio;
      audio.onended = () => {
        if (audio._blobUrl) URL.revokeObjectURL(audio._blobUrl);
        _playingAudio = null;
        resolve();
      };
      audio.onerror = () => { _playingAudio = null; resolve(); };
      audio.play().catch(resolve);
    });
  }

  async function _speakChunked(text, msgEl) {
    const btn = msgEl?.querySelector(".ai-play-btn");
    _stopPlayback = false;
    _setState("speaking");
    _setPlayBtn(btn, true);

    const chunks = _chunkText(_cleanText(text));
    for (const chunk of chunks) {
      if (_stopPlayback || _state !== "speaking") break;
      const audio = await _fetchTtsAudio(chunk);
      if (_stopPlayback) break;
      if (!audio) continue;   // TTS failed for this chunk — skip, don't abort
      await _playAudioObj(audio);
    }
    if (!_stopPlayback) { _setState("idle"); _setPlayBtn(btn, false); }
    _stopPlayback = false;
  }

  // text stored in data-speech to avoid HTML-quote-escaping issues
  window.toggleSpeech = async function (btn) {
    const text = btn.dataset.speech || "";
    if (!text) return;
    if (_playingAudio || _state === "speaking") {
      _stopPlayback = true;
      if (_playingAudio) {
        _playingAudio.pause();
        if (_playingAudio._blobUrl) URL.revokeObjectURL(_playingAudio._blobUrl);
        _playingAudio = null;
      }
      _setState("idle");
      _setPlayBtn(btn, false);
      return;
    }
    await _speakChunked(text, btn.closest(".ai-msg"));
  };

  // ── DOM helpers ───────────────────────────────────────────────
  function _appendUserMsg(text) {
    const el = document.createElement("div");
    el.className = "ai-msg user";
    el.innerHTML = `<div class="ai-avatar">👤</div><div class="ai-bubble">${_esc(text)}</div>`;
    feed()?.appendChild(el);
    _scrollFeed();
  }

  function _appendTyping() {
    const el = document.createElement("div");
    el.className = "ai-msg ai"; el.id = "typingIndicator";
    el.innerHTML = `<div class="ai-avatar">🤖</div><div class="ai-bubble"><div class="ai-typing"><span></span><span></span><span></span></div></div>`;
    feed()?.appendChild(el);
    _scrollFeed();
    return el;
  }

  function _appendAiMsg(text, toolsUsed) {
    const safeText = _esc(_cleanText(text)).replace(/`([^`]+)`/g, "<code>$1</code>");
    const tools = (toolsUsed || []).map(t => {
      const labels = { novelty: "🔍 Novelty", properties: "⚗️ Properties", validate: "✓ SMILES" };
      return `<span class="hint-chip" style="cursor:default;">${labels[t]||t}</span>`;
    }).join("");
    const el = document.createElement("div");
    el.className = "ai-msg ai";
    el.innerHTML = `
      <div class="ai-avatar">🤖</div>
      <div class="ai-bubble">
        <div>${safeText}</div>
        ${tools ? `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;">${tools}</div>` : ""}
        <button class="ai-play-btn" onclick="toggleSpeech(this)">▶ Play</button>
      </div>`;
    el.querySelector(".ai-play-btn").dataset.speech = text;
    feed()?.appendChild(el);
    _scrollFeed();
    return el;
  }

  function _setPlayBtn(btn, on) {
    if (!btn) return;
    btn.textContent = on ? "⏸ Pause" : "▶ Play";
    btn.classList.toggle("playing", on);
  }

  function _scrollFeed() { const f = feed(); if (f) f.scrollTop = f.scrollHeight; }

  function _esc(s) {
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
            .replace(/"/g,"&quot;").replace(/\n/g,"<br>");
  }

  // ── State machine ─────────────────────────────────────────────
  const _G_STATES  = { idle:"idle", recording:"listening", transcribing:"thinking", thinking:"thinking", speaking:"speaking" };
  const _G_LABELS  = { idle:"Tap mic to ask a question", recording:"Listening…", transcribing:"Transcribing…", thinking:"Thinking…", speaking:"Speaking…" };
  const _STATUS_TX = {
    idle:"", recording:'<span class="status-dot-live"></span> Recording… tap mic to stop',
    transcribing:"🎙 Transcribing…", thinking:"🤖 Thinking…", speaking:"🔊 Speaking…",
  };

  function _setState(s) {
    _state = s;
    if (window.GlobeViz) GlobeViz.setState(_G_STATES[s] || "idle");

    // Voice overlay
    const ov = voOverlay();
    if (ov) ov.dataset.state = _G_STATES[s] || "idle";
    const lbl = voLabel();
    if (lbl) lbl.textContent = _G_LABELS[s] || "";

    // Voice status
    _setVoStatus(_STATUS_TX[s] || "", s);

    // Both mic buttons
    [micGlobe(), micText()].forEach(m => {
      if (!m) return;
      m.classList.toggle("recording", s === "recording");
      m.textContent = s === "recording" ? "⏹" : "🎙";
      m.disabled = s === "transcribing" || s === "thinking" || s === "speaking";
    });

    // Text mode controls
    const st = txStatus();
    if (st) { st.innerHTML = _STATUS_TX[s] || ""; st.className = "askai-status " + s; }
    const sb = sendBtn(), ta = textarea();
    if (sb) sb.disabled = s === "thinking" || s === "speaking";
    if (ta) ta.disabled = s === "transcribing" || s === "thinking";
  }

  function _setVoStatus(msg, cls) {
    const el = voStatus();
    if (!el) return;
    el.innerHTML = msg;
    el.className = "vo-status " + (cls || "");
  }
})();
