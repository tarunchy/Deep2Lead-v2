/* Evaluate Fine-tune — comparison logic */

let _compareAbort = null;

async function runComparison() {
  const btn = document.getElementById("compareBtn");
  const progress = document.getElementById("compareProgress");
  const bar = document.getElementById("cmpBar");
  const lbl = document.getElementById("cmpLabel");
  const results = document.getElementById("compareResults");
  const orig = btn.innerHTML;

  btn.disabled = true;
  btn.innerHTML = '<span class="spin-icon"></span>Running both models…';
  progress.style.display = "block";
  results.style.display = "none";
  _compareAbort = new AbortController();

  const steps = [
    { pct: 10, label: "Sending prompt to both models…" },
    { pct: 35, label: "Production model generating…" },
    { pct: 55, label: "Fine-tuned model generating…" },
    { pct: 80, label: "Scoring & validating candidates…" },
    { pct: 95, label: "Building comparison report…" },
  ];
  let si = 0;
  const timer = setInterval(() => {
    if (si < steps.length) {
      bar.style.width = steps[si].pct + "%";
      lbl.textContent = steps[si].label;
      si++;
    }
  }, 2800);

  try {
    const payload = {
      smile: document.getElementById("seed_smiles").value.trim(),
      amino_acid_seq: document.getElementById("amino_acid_seq").value.trim(),
      num_candidates: parseInt(document.getElementById("num_candidates").value),
      noise: parseFloat(document.getElementById("noise_level").value),
      target_id: document.getElementById("target_id").value,
      target_name: document.getElementById("target_name_val").value,
      uniprot_id: document.getElementById("uniprot_id").value,
      pdb_id: document.getElementById("pdb_id").value,
    };

    const data = await apiFetch("/api/v2/compare-models", {
      method: "POST",
      body: JSON.stringify(payload),
      signal: _compareAbort.signal,
    });

    clearInterval(timer);
    bar.style.width = "100%";
    lbl.textContent = "Done!";

    renderResults(data);
    results.style.display = "block";
    results.scrollIntoView({ behavior: "smooth", block: "start" });

  } catch (e) {
    clearInterval(timer);
    if (e.name !== "AbortError") {
      bar.style.width = "0%";
      lbl.textContent = "Error: " + (e.message || "Unknown error");
      showAlert("Comparison failed: " + (e.message || "check server logs"), "danger");
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
    _compareAbort = null;
  }
}

function renderResults(data) {
  renderModelPanel("prod", data.production);
  renderModelPanel("ft",   data.finetuned);
  renderReport(data.comparison, data.production, data.finetuned);
}

function renderModelPanel(key, model) {
  const s = model.stats;
  const tableEl = document.getElementById(`${key}Table`);
  const statsEl = document.getElementById(`${key}Stats`);
  const errEl   = document.getElementById(`${key}Error`);

  if (errEl) errEl.style.display = model.error && !model.candidates.length ? "block" : "none";
  if (errEl && model.error) errEl.textContent = "Error: " + model.error;

  statsEl.innerHTML = `
    <div class="stat-row"><span class="label">Candidates found</span><span class="val">${s.valid_count}</span></div>
    <div class="stat-row"><span class="label">Avg QED</span><span class="val">${s.avg_qed.toFixed(3)}</span></div>
    <div class="stat-row"><span class="label">Avg SAS</span><span class="val">${s.avg_sas.toFixed(2)}</span></div>
    <div class="stat-row"><span class="label">Avg Score</span><span class="val">${(s.avg_composite * 100).toFixed(0)}%</span></div>
    <div class="stat-row"><span class="label">Latency</span><span class="val">${(model.latency_ms / 1000).toFixed(1)}s</span></div>
    <div class="stat-row"><span class="label">Uniqueness</span><span class="val">${(s.unique_rate * 100).toFixed(0)}%</span></div>
  `;

  if (!model.candidates.length) {
    tableEl.innerHTML = "<p style='color:var(--text-muted);padding:8px 0;font-size:.83rem;'>No valid candidates.</p>";
    return;
  }

  const SCORE_CLR = s => s >= 0.7 ? "#3fb950" : s >= 0.4 ? "#ffa657" : "#ff7b72";
  const rows = model.candidates.map(c => {
    const short = c.smiles.length > 22 ? c.smiles.slice(0, 22) + "…" : c.smiles;
    return `<tr onclick="copySmiles('${c.smiles.replace(/'/g, "\\'")}')" title="Click to copy SMILES">
      <td>${c.rank}</td>
      <td style="font-family:monospace;font-size:.72rem;">${short}</td>
      <td style="color:${SCORE_CLR(c.composite_score)};font-weight:700;">${(c.composite_score * 100).toFixed(0)}%</td>
      <td>${c.qed != null ? c.qed.toFixed(2) : "—"}</td>
      <td>${c.sas != null ? c.sas.toFixed(1) : "—"}</td>
      <td>${c.lipinski_pass ? "✅" : "❌"}</td>
    </tr>`;
  }).join("");

  tableEl.innerHTML = `
    <div style="overflow-x:auto;">
      <table class="cmp-candidate-table">
        <thead><tr><th>#</th><th>SMILES</th><th>Score</th><th>QED</th><th>SAS</th><th>Lipinski</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function renderReport(cmp, prod, ft) {
  const banner = document.getElementById("winnerBanner");
  const metricsEl = document.getElementById("metricGrid");

  const names = { production: "Production (dlyog04)", finetuned: "Fine-tuned (dgx1)", tie: "Tie" };
  const cls   = { production: "winner-production",    finetuned: "winner-finetuned",   tie: "winner-tie" };

  banner.className = "report-winner-banner " + cls[cmp.overall_winner];
  banner.innerHTML = `Overall Winner: <strong>${names[cmp.overall_winner]}</strong>
    <span style="font-size:.8rem;font-weight:400;margin-left:12px;">
      Prod ${(cmp.production_score * 100).toFixed(0)}% &nbsp;|&nbsp; FT ${(cmp.finetuned_score * 100).toFixed(0)}%
    </span>`;

  const metrics = [
    { name: "SMILES Validity",  key: "validity",    prodVal: cmp.validity_prod + "%",     ftVal: cmp.validity_ft + "%" },
    { name: "Avg QED",          key: "avg_qed",     prodVal: prod.stats.avg_qed.toFixed(3), ftVal: ft.stats.avg_qed.toFixed(3) },
    { name: "Avg SAS",          key: "avg_sas",     prodVal: prod.stats.avg_sas.toFixed(2), ftVal: ft.stats.avg_sas.toFixed(2) },
    { name: "Avg Score",        key: "composite",   prodVal: (prod.stats.avg_composite * 100).toFixed(0) + "%", ftVal: (ft.stats.avg_composite * 100).toFixed(0) + "%" },
    { name: "Uniqueness",       key: "unique_rate", prodVal: (prod.stats.unique_rate * 100).toFixed(0) + "%",   ftVal: (ft.stats.unique_rate * 100).toFixed(0) + "%" },
    { name: "Speed",            key: "latency",     prodVal: (prod.latency_ms / 1000).toFixed(1) + "s",         ftVal: (ft.latency_ms / 1000).toFixed(1) + "s" },
  ];

  const winCls = { production: "prod", finetuned: "ft", tie: "tie" };
  const winLabel = { production: "Prod wins", finetuned: "FT wins", tie: "Tie" };

  metricsEl.innerHTML = metrics.map(m => {
    const w = cmp.wins[m.key];
    return `<div class="metric-card">
      <div class="metric-name">${m.name}</div>
      <div class="metric-winner ${winCls[w]}">${winLabel[w]}</div>
      <div class="metric-vals">Prod: ${m.prodVal} &nbsp; FT: ${m.ftVal}</div>
    </div>`;
  }).join("");

  document.getElementById("reportCard").style.display = "block";
}

function copySmiles(smiles) {
  navigator.clipboard.writeText(smiles).then(() => {
    showAlert("SMILES copied to clipboard!", "success");
  }).catch(() => {
    showAlert("Copy failed — SMILES: " + smiles, "info");
  });
}

async function loadModelHealth() {
  try {
    const data = await apiFetch("/api/v2/model-health");
    _setHealthDot("prodDot", data.production);
    _setHealthDot("ftDot",   data.finetuned);
    _setHealthLabel("prodStatus", data.production, "dlyog04:9000");
    _setHealthLabel("ftStatus",   data.finetuned,  "dgx1:9002");
  } catch (_) {}
}

function _setHealthDot(id, up) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = "health-dot " + (up ? "up" : "down");
  el.title = up ? "Online" : "Offline";
}

function _setHealthLabel(id, up, host) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = host + " — " + (up ? "Online" : "Offline");
  el.style.color = up ? "#3fb950" : "#ff7b72";
}
