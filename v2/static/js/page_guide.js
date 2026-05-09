/* page_guide.js — Demo-style tour: animated cursor + click ripples + Kokoro TTS */
(function () {
  "use strict";

  let _steps  = [];
  let _opts   = {};
  let _step   = -1;
  let _audio  = null;
  let _busy   = false;
  let _muted  = false;
  let _cx = 200, _cy = 200;   // current cursor position

  // ── Public ────────────────────────────────────────────────────
  window.GuideEngine = {
    init(cfg) {
      if (!cfg?.steps?.length) return;
      _steps = cfg.steps;
      _opts  = { title: cfg.title || "Tour", character: cfg.character || "🎓", voice: cfg.voice || "af_heart" };
      _buildDOM();
      _buildFab();
    },
  };

  // ── Build DOM ─────────────────────────────────────────────────
  function _buildDOM() {
    ["guideCursor","guideRippleLayer","guideHighlight","guidePanel"].forEach(id => document.getElementById(id)?.remove());

    // Cursor SVG
    const cur = document.createElement("div");
    cur.id = "guideCursor";
    cur.innerHTML = `<svg width="22" height="26" viewBox="0 0 22 26" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 2L3 21L7.5 16.5L11 24L13.5 23L10 15.5L18 15.5L3 2Z"
        fill="white" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/>
    </svg>`;
    document.body.appendChild(cur);

    // Ripple layer
    const rl = document.createElement("div");
    rl.id = "guideRippleLayer";
    document.body.appendChild(rl);

    // Element highlight ring
    const hl = document.createElement("div");
    hl.id = "guideHighlight";
    document.body.appendChild(hl);

    // Dot progress HTML
    const dots = _steps.map((_, i) => `<div class="gp-dot" id="gd${i}"></div>`).join("");

    // Narration panel
    const panel = document.createElement("div");
    panel.id = "guidePanel";
    panel.innerHTML = `
      <div class="gp-body">
        <div class="gp-char-wrap">
          <div class="gp-char" id="gpChar">${_opts.character}</div>
          <div class="gp-waves" id="gpWaves">
            ${[0,1,2,3,4].map((_,i)=>`<div class="gp-wave" style="animation-delay:${i*.12}s"></div>`).join("")}
          </div>
        </div>
        <div class="gp-text" id="gpText">Click ❓ to start the guided demo.</div>
      </div>
      <div class="gp-footer">
        <div class="gp-dots" id="gpDots">${dots}</div>
        <button class="gp-btn gp-btn-mute" id="gpMute" title="Toggle audio">🔊</button>
        <button class="gp-btn" id="gpReplay" title="Replay step">↺</button>
        <button class="gp-btn" id="gpPrev">‹ Back</button>
        <button class="gp-btn gp-btn-primary" id="gpNext">Next ›</button>
        <button class="gp-btn gp-btn-mute" id="gpClose" title="Close tour">✕</button>
      </div>`;
    document.body.appendChild(panel);

    document.getElementById("gpClose").onclick  = _close;
    document.getElementById("gpNext").onclick   = () => _step < _steps.length - 1 ? _goTo(_step + 1) : _close();
    document.getElementById("gpPrev").onclick   = () => _step > 0 && _goTo(_step - 1);
    document.getElementById("gpReplay").onclick = () => _step >= 0 && _playStep(_steps[_step]);
    document.getElementById("gpMute").onclick   = _toggleMute;
  }

  function _buildFab() {
    document.getElementById("guideFab")?.remove();
    const b = document.createElement("button");
    b.id = "guideFab";
    b.className = "guide-fab";
    b.title = "Start interactive tour";
    b.textContent = "❓";
    b.onclick = () => _open(0);
    document.body.appendChild(b);
  }

  // ── Open / Close ──────────────────────────────────────────────
  function _open(idx) {
    document.getElementById("guideCursor").style.display = "block";
    document.getElementById("guidePanel").style.display  = "block";
    // Place cursor in upper-right of content area to start
    _setCursor(window.innerWidth * 0.6, window.innerHeight * 0.25, false);
    _goTo(idx);
  }

  function _close() {
    _stopAudio();
    ["guideCursor","guideHighlight","guidePanel"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = "none";
    });
    document.getElementById("guideRippleLayer").innerHTML = "";
    _step = -1;
  }

  // ── Step playback ─────────────────────────────────────────────
  async function _goTo(idx) {
    _stopAudio();
    _step = idx;
    const s = _steps[idx];

    // Update text & dots
    document.getElementById("gpText").textContent = s.bubble || s.text.slice(0, 120) + "…";
    _updateDots(idx);

    const nextBtn = document.getElementById("gpNext");
    const prevBtn = document.getElementById("gpPrev");
    nextBtn.textContent = idx === _steps.length - 1 ? "✓ Done" : "Next ›";
    prevBtn.disabled = idx === 0;

    await _playStep(s);
  }

  async function _playStep(s) {
    if (_busy) return;
    _busy = true;
    document.getElementById("gpNext").disabled = true;

    try {
      // Kick off TTS fetch in parallel with cursor movement
      const audioPromise = _muted ? Promise.resolve(null) : _fetchAudio(s.text);

      // Move cursor to target element
      if (s.target) await _animateCursorTo(s.target, s.action !== "none");

      // Highlight the element
      if (s.target) _highlightEl(s.target);

      // Wait for audio then play it
      const audioObj = await audioPromise;
      if (audioObj) {
        _setWaves(true);
        await _playAudioObj(audioObj);
        _setWaves(false);
      }

      // Brief pause before enabling next
      await _wait(600);

    } catch (e) { /* silent */ } finally {
      _busy = false;
      document.getElementById("gpNext").disabled = false;
    }
  }

  // ── Cursor animation ──────────────────────────────────────────
  function _setCursor(x, y, animate) {
    const el = document.getElementById("guideCursor");
    if (!el) return;
    if (!animate) {
      el.style.transition = "none";
      el.style.left = x + "px";
      el.style.top  = y + "px";
    } else {
      el.style.transition = "left .72s cubic-bezier(.4,0,.2,1), top .72s cubic-bezier(.4,0,.2,1)";
      el.style.left = x + "px";
      el.style.top  = y + "px";
    }
    _cx = x; _cy = y;
  }

  function _animateCursorTo(selector, doClick) {
    return new Promise(resolve => {
      const el = document.querySelector(selector);
      if (!el) { resolve(); return; }

      el.scrollIntoView({ behavior: "smooth", block: "center" });

      // Wait for scroll to settle before computing position
      setTimeout(() => {
        const r = el.getBoundingClientRect();
        const tx = r.left + r.width * 0.35;
        const ty = r.top  + r.height * 0.45;
        _setCursor(tx, ty, true);

        // After cursor arrives, optionally click
        setTimeout(() => {
          if (doClick !== false) _doClick(tx, ty);
          resolve();
        }, 780);
      }, 350);
    });
  }

  // ── Click ripple ──────────────────────────────────────────────
  function _doClick(x, y) {
    const layer = document.getElementById("guideRippleLayer");
    if (!layer) return;

    [false, true].forEach((inner, i) => {
      const r = document.createElement("div");
      r.className = inner ? "guide-ripple-inner" : "guide-ripple";
      r.style.left = x + "px";
      r.style.top  = y + "px";
      layer.appendChild(r);
      setTimeout(() => r.remove(), inner ? 320 : 600);
    });
  }

  // ── Element highlight ─────────────────────────────────────────
  function _highlightEl(selector) {
    const hl = document.getElementById("guideHighlight");
    const el = document.querySelector(selector);
    if (!hl || !el) return;
    const r = el.getBoundingClientRect();
    const p = 5;
    Object.assign(hl.style, {
      display: "block",
      top:    `${r.top  - p}px`,
      left:   `${r.left - p}px`,
      width:  `${r.width  + p * 2}px`,
      height: `${r.height + p * 2}px`,
    });
    // Auto-clear after 3 seconds
    setTimeout(() => { if (hl) hl.style.display = "none"; }, 3000);
  }

  // ── Dot progress ──────────────────────────────────────────────
  function _updateDots(activeIdx) {
    _steps.forEach((_, i) => {
      const d = document.getElementById(`gd${i}`);
      if (!d) return;
      d.className = "gp-dot" + (i < activeIdx ? " done" : i === activeIdx ? " active" : "");
    });
  }

  // ── Audio ─────────────────────────────────────────────────────
  async function _fetchAudio(text) {
    try {
      const res = await fetch("/api/v2/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: _opts.voice, speed: 0.92 }),
      });
      if (!res.ok) return null;
      const url = URL.createObjectURL(await res.blob());
      const a   = new Audio(url);
      a._blobUrl = url;
      return a;
    } catch { return null; }
  }

  function _playAudioObj(a) {
    return new Promise(resolve => {
      _audio = a;
      a.onended = () => { _cleanup(a); resolve(); };
      a.onerror = () => { _cleanup(a); resolve(); };
      a.play().catch(() => { _cleanup(a); resolve(); });
    });
  }

  function _cleanup(a) {
    if (a?._blobUrl) URL.revokeObjectURL(a._blobUrl);
    _audio = null;
  }

  function _stopAudio() {
    if (_audio) { _audio.pause(); _cleanup(_audio); }
    _setWaves(false);
    _busy = false;
  }

  function _toggleMute() {
    _muted = !_muted;
    document.getElementById("gpMute").textContent = _muted ? "🔇" : "🔊";
    if (_muted && _audio) _stopAudio();
  }

  function _setWaves(on) {
    document.getElementById("gpWaves")?.classList.toggle("active", on);
  }

  function _wait(ms) { return new Promise(r => setTimeout(r, ms)); }

  // ── Auto-init ─────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    if (window.PAGE_GUIDE) GuideEngine.init(window.PAGE_GUIDE);
  });
})();
