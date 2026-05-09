/* page_guide.js — Demo tour: animated cursor + click ripples + Kokoro TTS + auto-advance */
(function () {
  "use strict";

  let _steps     = [];
  let _opts      = {};
  let _step      = -1;
  let _audio     = null;
  let _busy      = false;
  let _paused    = false;
  let _nextTimer = null;
  let _cx = 200, _cy = 200;

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

  // ── DOM ───────────────────────────────────────────────────────
  function _buildDOM() {
    ["guideCursor","guideRippleLayer","guideHighlight","guidePanel"].forEach(id => document.getElementById(id)?.remove());

    // Cursor SVG
    const cur = document.createElement("div");
    cur.id = "guideCursor";
    cur.innerHTML = `<svg width="22" height="26" viewBox="0 0 22 26" fill="none">
      <path d="M3 2L3 21L7.5 16.5L11 24L13.5 23L10 15.5L18 15.5L3 2Z"
        fill="white" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/>
    </svg>`;
    document.body.appendChild(cur);

    // Ripple + highlight layers
    const rl = document.createElement("div"); rl.id = "guideRippleLayer"; document.body.appendChild(rl);
    const hl = document.createElement("div"); hl.id = "guideHighlight";   document.body.appendChild(hl);

    // Dots
    const dots = _steps.map((_, i) => `<div class="gp-dot" id="gd${i}"></div>`).join("");

    // Panel
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
        <button class="gp-btn" id="gpReplay" title="Replay this step">↺</button>
        <button class="gp-btn" id="gpSkip"   title="Skip to next step">Skip ›</button>
        <button class="gp-btn gp-btn-pause"  id="gpPause">⏸ Pause</button>
        <button class="gp-btn gp-btn-mute"   id="gpMute"  title="Toggle audio">🔊</button>
        <button class="gp-btn gp-btn-mute"   id="gpClose" title="Close">✕</button>
      </div>`;
    document.body.appendChild(panel);

    document.getElementById("gpClose").onclick  = _close;
    document.getElementById("gpSkip").onclick   = _skip;
    document.getElementById("gpReplay").onclick = _replay;
    document.getElementById("gpPause").onclick  = _togglePause;
    document.getElementById("gpMute").onclick   = _toggleMute;
  }

  function _buildFab() {
    document.getElementById("guideFab")?.remove();
    const b = document.createElement("button");
    b.id = "guideFab"; b.className = "guide-fab";
    b.title = "Start interactive tour"; b.textContent = "❓";
    b.onclick = () => _open(0);
    document.body.appendChild(b);
  }

  // ── Open / Close ──────────────────────────────────────────────
  function _open(idx) {
    _paused = false;
    document.getElementById("guideCursor").style.display = "block";
    document.getElementById("guidePanel").style.display  = "block";
    _setCursor(window.innerWidth * 0.6, window.innerHeight * 0.25, false);
    _goTo(idx);
  }

  function _close() {
    _clearNext();
    _stopAudio();
    ["guideCursor","guideHighlight","guidePanel"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = "none";
    });
    document.getElementById("guideRippleLayer").innerHTML = "";
    _step = -1; _paused = false;
  }

  // ── Navigation ────────────────────────────────────────────────
  function _skip() {
    // Skip to next immediately, regardless of audio/pause state
    _clearNext();
    _stopAudio();
    _paused = false;
    _setPauseUI(false);
    if (_step < _steps.length - 1) _goTo(_step + 1);
    else _close();
  }

  function _replay() {
    _clearNext();
    _stopAudio();
    _paused = false;
    _busy = false;
    _setPauseUI(false);
    if (_step >= 0) _playStep(_steps[_step]);
  }

  async function _goTo(idx) {
    _clearNext();
    _stopAudio();
    _step = idx;
    const s = _steps[idx];

    document.getElementById("gpText").textContent = s.bubble || s.text.slice(0, 120) + "…";
    _updateDots(idx);
    document.getElementById("gpSkip").textContent = idx === _steps.length - 1 ? "Finish ✓" : "Skip ›";

    await _playStep(s);

    // Auto-advance after audio ends (only if not paused and step hasn't changed externally)
    if (!_paused && _step === idx) {
      _scheduleNext();
    }
  }

  async function _playStep(s) {
    if (_busy) return;
    _busy = true;

    try {
      const audioPromise = _fetchAudio(s.text);

      if (s.target) await _animateCursorTo(s.target, s.action !== "none");
      if (s.target) _highlightEl(s.target);

      const audioObj = await audioPromise;
      if (audioObj && !_paused) {
        _setWaves(true);
        await _playAudioObj(audioObj);
        _setWaves(false);
      }
    } catch (e) { /* silent */ } finally {
      _busy = false;
    }
  }

  // ── Auto-advance ──────────────────────────────────────────────
  function _scheduleNext() {
    _clearNext();
    _nextTimer = setTimeout(() => {
      if (_paused) return;
      if (_step < _steps.length - 1) _goTo(_step + 1);
      else _close();
    }, 1400);
  }

  function _clearNext() {
    if (_nextTimer) { clearTimeout(_nextTimer); _nextTimer = null; }
  }

  // ── Pause / Resume ────────────────────────────────────────────
  function _togglePause() {
    if (!_paused) {
      // Pause
      _paused = true;
      _clearNext();
      if (_audio && !_audio.paused) _audio.pause();
      _setWaves(false);
      _setPauseUI(true);
    } else {
      // Resume
      _paused = false;
      _setPauseUI(false);
      if (_audio && _audio.paused && _audio.currentTime > 0 && !_audio.ended) {
        // Audio was mid-play — resume it; onended will schedule next
        _audio.play().then(() => _setWaves(true)).catch(() => {});
      } else if (_step >= 0) {
        // Audio already ended or never played — replay this step
        _busy = false;
        _playStep(_steps[_step]).then(() => {
          if (!_paused && _step >= 0) _scheduleNext();
        });
      }
    }
  }

  function _setPauseUI(paused) {
    const btn = document.getElementById("gpPause");
    if (!btn) return;
    btn.textContent = paused ? "▶ Resume" : "⏸ Pause";
    btn.className   = paused ? "gp-btn gp-btn-resume" : "gp-btn gp-btn-pause";
  }

  // ── Cursor ────────────────────────────────────────────────────
  function _setCursor(x, y, animate) {
    const el = document.getElementById("guideCursor");
    if (!el) return;
    el.style.transition = animate
      ? "left .72s cubic-bezier(.4,0,.2,1), top .72s cubic-bezier(.4,0,.2,1)"
      : "none";
    el.style.left = x + "px";
    el.style.top  = y + "px";
    _cx = x; _cy = y;
  }

  function _animateCursorTo(selector, doClick) {
    return new Promise(resolve => {
      const el = document.querySelector(selector);
      if (!el) { resolve(); return; }
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => {
        const r  = el.getBoundingClientRect();
        const tx = r.left + r.width  * 0.35;
        const ty = r.top  + r.height * 0.45;
        _setCursor(tx, ty, true);
        setTimeout(() => {
          if (doClick !== false) _doClick(tx, ty);
          resolve();
        }, 780);
      }, 350);
    });
  }

  // ── Ripple ────────────────────────────────────────────────────
  function _doClick(x, y) {
    const layer = document.getElementById("guideRippleLayer");
    if (!layer) return;
    [false, true].forEach(inner => {
      const r = document.createElement("div");
      r.className = inner ? "guide-ripple-inner" : "guide-ripple";
      r.style.left = x + "px"; r.style.top = y + "px";
      layer.appendChild(r);
      setTimeout(() => r.remove(), inner ? 320 : 600);
    });
  }

  // ── Highlight ─────────────────────────────────────────────────
  function _highlightEl(selector) {
    const hl = document.getElementById("guideHighlight");
    const el = document.querySelector(selector);
    if (!hl || !el) return;
    const r = el.getBoundingClientRect(), p = 5;
    Object.assign(hl.style, {
      display: "block",
      top:    `${r.top  - p}px`,  left:   `${r.left - p}px`,
      width:  `${r.width  + p * 2}px`, height: `${r.height + p * 2}px`,
    });
    setTimeout(() => { if (hl) hl.style.display = "none"; }, 3000);
  }

  // ── Dots ──────────────────────────────────────────────────────
  function _updateDots(activeIdx) {
    _steps.forEach((_, i) => {
      const d = document.getElementById(`gd${i}`);
      if (d) d.className = "gp-dot" + (i < activeIdx ? " done" : i === activeIdx ? " active" : "");
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
      a.onended = () => { _cleanup(a); _setWaves(false); resolve(); };
      a.onerror = () => { _cleanup(a); resolve(); };
      a.play().catch(() => { _cleanup(a); resolve(); });
    });
  }

  function _cleanup(a) {
    if (a?._blobUrl) URL.revokeObjectURL(a._blobUrl);
    if (_audio === a) _audio = null;
  }

  function _stopAudio() {
    if (_audio) { _audio.pause(); _cleanup(_audio); }
    _setWaves(false);
    _busy = false;
  }

  function _toggleMute() {
    const muted = document.getElementById("gpMute").textContent === "🔇";
    document.getElementById("gpMute").textContent = muted ? "🔊" : "🔇";
    if (_audio) _audio.muted = !muted;
  }

  function _setWaves(on) {
    document.getElementById("gpWaves")?.classList.toggle("active", on);
  }

  // ── Auto-init ─────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    if (window.PAGE_GUIDE) GuideEngine.init(window.PAGE_GUIDE);
  });
})();
