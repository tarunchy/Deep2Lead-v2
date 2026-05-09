/* Auto Experiment: SSE stream handler, round rendering, score chart */
(function () {
  "use strict";

  let _eventSource = null;
  let _rounds = [];
  let _maxScore = 0;

  window.AutoExp = {
    start: async function (config) {
      const btn = document.getElementById("startAutoBtn");
      const stopBtn = document.getElementById("stopAutoBtn");
      if (btn) btn.disabled = true;
      if (stopBtn) stopBtn.disabled = false;

      setStatus("starting", "Starting Auto Experiment…");
      _rounds = [];
      _maxScore = 0;

      try {
        const res = await apiFetch("/api/v3/auto-experiment/start", { method: "POST", body: JSON.stringify(config) });
        if (res.error) { setStatus("failed", res.error); return; }
        AutoExp.stream(res.run_id);
        // Store run_id for stop button
        document.getElementById("currentRunId").value = res.run_id;
      } catch (e) {
        setStatus("failed", "Failed to start: " + e.message);
        if (btn) btn.disabled = false;
      }
    },

    stream: function (runId) {
      if (_eventSource) _eventSource.close();
      _eventSource = new EventSource(`/api/v3/auto-experiment/${runId}/stream`);

      _eventSource.onmessage = function (e) {
        const msg = JSON.parse(e.data);
        if (msg.type === "log") appendLog(msg.message);
        else if (msg.type === "round") addRound(msg.round);
        else if (msg.type === "state") updateStatePanel(msg);
        else if (msg.type === "done") onDone(msg.status);
      };

      _eventSource.onerror = function () {
        setStatus("failed", "Connection lost.");
        _eventSource.close();
      };
    },

    stop: async function () {
      const runId = document.getElementById("currentRunId")?.value;
      if (!runId) return;
      await apiFetch(`/api/v3/auto-experiment/${runId}/stop`, { method: "POST" });
      if (_eventSource) _eventSource.close();
      setStatus("stopped", "Stopped by user.");
      const stopBtn = document.getElementById("stopAutoBtn");
      if (stopBtn) stopBtn.disabled = true;
    },
  };

  function setStatus(status, msg) {
    const dot = document.getElementById("statusDot");
    const txt = document.getElementById("statusText");
    if (dot) { dot.className = "status-dot " + status; }
    if (txt) txt.textContent = msg || status;
  }

  function appendLog(msg) {
    const console = document.getElementById("logConsole");
    if (!console) return;
    const line = document.createElement("div");
    line.className = "log-line" + (msg.includes("IMPROVED") ? " improved" : msg.includes("error") ? " error" : "");
    line.textContent = msg;
    console.appendChild(line);
    console.scrollTop = console.scrollHeight;
  }

  function addRound(round) {
    _rounds.push(round);
    if (round.best_score > _maxScore) _maxScore = round.best_score;
    renderRounds();
    renderChart();
    // Update best mol
    if (round.improved && round.candidates && round.candidates[0]) {
      const bestMol = document.getElementById("bestMolSmiles");
      const bestScore = document.getElementById("bestMolScore");
      if (bestMol) bestMol.textContent = round.candidates[0].smiles;
      if (bestScore) bestScore.textContent = (round.best_score * 100).toFixed(1) + "%";
      if (window.updateBossBar) updateBossBar(round.best_score);
    }
  }

  function renderRounds() {
    const feed = document.getElementById("roundFeed");
    if (!feed) return;
    feed.innerHTML = _rounds.map(r => {
      const icon = r.status === "keep" ? "✅" : r.status === "discard" ? "↩️" : "❌";
      const cls = r.status === "keep" ? "kept" : r.status === "discard" ? "discard" : "failed";
      const delta = r.improved ? `<span class="score-up">↑ ${(r.best_score * 100).toFixed(1)}%</span>` : `<span class="score-same">No improvement</span>`;
      return `<div class="round-card ${cls}">
        <div class="round-icon">${icon}</div>
        <div class="round-body">
          <div class="round-title">Round ${r.round_num} — ${r.status.toUpperCase()}</div>
          <div class="round-rationale">${r.rationale || ""}</div>
          <div class="round-score">${delta} · ${r.candidates_tried || 0} molecules tried</div>
        </div>
      </div>`;
    }).reverse().join("");
  }

  function renderChart() {
    const bars = document.getElementById("chartBars");
    if (!bars || !_rounds.length) return;
    const maxH = 80;
    bars.innerHTML = _rounds.map(r => {
      const h = _maxScore > 0 ? Math.max(4, Math.round((r.best_score / _maxScore) * maxH)) : 4;
      const cls = r.status === "keep" ? "kept" : "discard";
      return `<div class="chart-bar ${cls}" style="height:${h}px;" data-score="${(r.best_score * 100).toFixed(1)}%" title="Round ${r.round_num}: ${(r.best_score * 100).toFixed(1)}%"></div>`;
    }).join("");
  }

  function updateStatePanel(msg) {
    const rcLabel = document.getElementById("roundsCompletedLabel");
    const bsLabel = document.getElementById("bestScoreLabel");
    if (rcLabel) rcLabel.textContent = msg.rounds_completed || 0;
    if (bsLabel && msg.best_score != null) bsLabel.textContent = (msg.best_score * 100).toFixed(1) + "%";
    setStatus(msg.status === "running" ? "running" : "idle", msg.status === "running" ? "Running…" : msg.status);
  }

  function onDone(status) {
    setStatus(status, status === "complete" ? "Complete!" : status);
    const stopBtn = document.getElementById("stopAutoBtn");
    const startBtn = document.getElementById("startAutoBtn");
    if (stopBtn) stopBtn.disabled = true;
    if (startBtn) startBtn.disabled = false;
    if (_eventSource) _eventSource.close();
    appendLog(`Auto Experiment ${status}.`);
  }
})();
