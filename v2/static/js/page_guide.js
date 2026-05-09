/* page_guide.js — Interactive spotlight tour engine with Kokoro TTS */
(function () {
  "use strict";

  let _steps = [];
  let _opts  = {};
  let _step  = -1;
  let _audio = null;
  let _busy  = false;

  // ── Public ────────────────────────────────────────────────────
  window.GuideEngine = {
    init: function (cfg) {
      if (!cfg || !cfg.steps || !cfg.steps.length) return;
      _steps = cfg.steps;
      _opts  = { title: cfg.title || "Guide", character: cfg.character || "🎓", voice: cfg.voice || "af_heart" };
      _buildDOM();
      _buildFab();
    },
    open: function (idx) { _open(idx || 0); },
  };

  // ── DOM ───────────────────────────────────────────────────────
  function _buildDOM() {
    ["guideSpotlight", "guidePanel"].forEach(id => document.getElementById(id)?.remove());

    // Spotlight overlay element (box-shadow trick)
    const spot = Object.assign(document.createElement("div"), { id: "guideSpotlight" });
    document.body.appendChild(spot);

    // Guide panel
    const panel = document.createElement("div");
    panel.id = "guidePanel";
    panel.innerHTML = `
      <div class="guide-header">
        <div class="guide-char-wrap">
          <div class="guide-char" id="gChar">${_opts.character}</div>
          <div class="guide-waves" id="gWaves">
            ${[0,1,2,3,4].map(i => `<div class="guide-wave" style="animation-delay:${i*.1}s"></div>`).join("")}
          </div>
        </div>
        <div class="guide-title-wrap">
          <div class="guide-title">${_opts.title}</div>
          <div class="guide-counter" id="gCounter">Step 1 of ${_steps.length}</div>
        </div>
        <button class="guide-close" id="gClose" title="Close guide">✕</button>
      </div>
      <div class="guide-bubble" id="gBubble"></div>
      <div class="guide-footer">
        <button class="guide-btn" id="gPrev" disabled>← Back</button>
        <button class="guide-btn guide-btn-audio" id="gAudio">🔊 Listen</button>
        <div class="guide-dot-track" id="gDots"></div>
        <button class="guide-btn guide-btn-primary" id="gNext">Next →</button>
      </div>`;
    document.body.appendChild(panel);

    // Dot track
    const dots = document.getElementById("gDots");
    _steps.forEach((_, i) => {
      const d = document.createElement("div");
      d.className = "guide-dot";
      d.id = `gDot${i}`;
      dots.appendChild(d);
    });

    document.getElementById("gClose").onclick = _close;
    document.getElementById("gNext").onclick  = _next;
    document.getElementById("gPrev").onclick  = _prev;
    document.getElementById("gAudio").onclick = _toggleAudio;
  }

  function _buildFab() {
    document.getElementById("guideFab")?.remove();
    const btn = Object.assign(document.createElement("button"), {
      id: "guideFab", className: "guide-fab", title: "Guided tour", innerHTML: "❓"
    });
    btn.onclick = () => _open(0);
    document.body.appendChild(btn);
  }

  // ── Navigation ────────────────────────────────────────────────
  function _open(idx) {
    document.getElementById("guidePanel").style.display = "block";
    _goTo(idx);
  }

  function _close() {
    _stopAudio();
    document.getElementById("guidePanel").style.display = "none";
    _clearSpotlight();
    _step = -1;
  }

  function _next() {
    if (_step < _steps.length - 1) _goTo(_step + 1);
    else _close();
  }

  function _prev() {
    if (_step > 0) _goTo(_step - 1);
  }

  function _goTo(idx) {
    _stopAudio();
    _step = idx;
    const s = _steps[idx];

    document.getElementById("gCounter").textContent = `Step ${idx + 1} of ${_steps.length}`;
    document.getElementById("gBubble").textContent  = s.bubble || s.text.slice(0, 140) + "…";
    document.getElementById("gPrev").disabled = idx === 0;
    document.getElementById("gNext").textContent = idx === _steps.length - 1 ? "Finish ✓" : "Next →";

    // Dots
    _steps.forEach((_, i) => {
      const d = document.getElementById(`gDot${i}`);
      if (d) d.className = "guide-dot" + (i === idx ? " active" : "");
    });

    _spotlight(s.highlight);
    _playAudio(s.text);
  }

  // ── Spotlight ─────────────────────────────────────────────────
  function _spotlight(selector) {
    const spot = document.getElementById("guideSpotlight");
    if (!selector) { _clearSpotlight(); return; }
    const el = document.querySelector(selector);
    if (!el) { _clearSpotlight(); return; }

    el.scrollIntoView({ behavior: "smooth", block: "center" });

    // Recompute after scroll settles
    setTimeout(() => {
      const r = el.getBoundingClientRect();
      const p = 10;
      Object.assign(spot.style, {
        display: "block",
        top:    `${r.top  - p}px`,
        left:   `${r.left - p}px`,
        width:  `${r.width  + p * 2}px`,
        height: `${r.height + p * 2}px`,
        boxShadow: "0 0 0 9999px rgba(0,0,0,0.50)",
      });
    }, 340);
  }

  function _clearSpotlight() {
    const spot = document.getElementById("guideSpotlight");
    if (spot) spot.style.display = "none";
  }

  // ── Audio ─────────────────────────────────────────────────────
  async function _playAudio(text) {
    if (_busy) return;
    _busy = true;
    _setAudioBtn("loading");

    try {
      const res = await fetch("/api/v2/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: _opts.voice, speed: 0.92 }),
      });
      if (!res.ok) throw new Error("TTS unavailable");
      const url = URL.createObjectURL(await res.blob());
      _audio = new Audio(url);
      _audio.onended = () => { _setAudioBtn("idle"); URL.revokeObjectURL(url); };
      _audio.onerror = () => _setAudioBtn("idle");
      await _audio.play();
      _setAudioBtn("playing");
    } catch {
      _setAudioBtn("idle");
    } finally {
      _busy = false;
    }
  }

  function _stopAudio() {
    if (_audio) { _audio.pause(); _audio.src = ""; _audio = null; }
    _setAudioBtn("idle");
    _busy = false;
  }

  function _toggleAudio() {
    if (_audio && !_audio.paused) _stopAudio();
    else if (_step >= 0) _playAudio(_steps[_step].text);
  }

  function _setAudioBtn(state) {
    const btn   = document.getElementById("gAudio");
    const waves = document.getElementById("gWaves");
    if (!btn) return;
    const map = { loading: ["⏳ Loading…", true, false], playing: ["⏸ Pause", false, true], idle: ["🔊 Listen", false, false] };
    const [label, disabled, wavesOn] = map[state] || map.idle;
    btn.textContent = label;
    btn.disabled    = disabled;
    if (waves) waves.classList.toggle("active", wavesOn);
  }

  // ── Auto-init if PAGE_GUIDE defined ──────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    if (window.PAGE_GUIDE) GuideEngine.init(window.PAGE_GUIDE);
  });
})();
