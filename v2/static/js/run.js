const form = document.getElementById("run-form");
const resultsSection = document.getElementById("results-section");
const resultsBody = document.getElementById("results-body");
const noiseVal = document.getElementById("noise-val");
const noiseInput = document.getElementById("noise");
const seedPreview = document.getElementById("seed-preview");
const seedSmileInput = document.getElementById("seed_smile");
const experimentIdInput = document.getElementById("experiment-id");
const publishBtn = document.getElementById("publish-btn");
const titleInput = document.getElementById("exp-title");
const hypothesisInput = document.getElementById("exp-hypothesis");

// Live noise value display
noiseInput?.addEventListener("input", () => {
  noiseVal.textContent = parseFloat(noiseInput.value).toFixed(2);
});

// Live seed SMILES preview
let previewTimer;
seedSmileInput?.addEventListener("input", () => {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => renderSeedPreview(), 800);
});

function renderSeedPreview() {
  const smiles = seedSmileInput.value.trim();
  if (!smiles) { seedPreview.innerHTML = ""; return; }
  const img = document.createElement("img");
  img.src = molSvgUrl(smiles);
  img.alt = smiles;
  img.onerror = () => { seedPreview.innerHTML = '<span class="text-muted text-sm">Invalid SMILES</span>'; };
  seedPreview.innerHTML = "";
  seedPreview.appendChild(img);
}

// Form submit
form?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = form.querySelector('button[type=submit]');
  setLoading(btn, true);
  resultsSection.style.display = "none";

  try {
    const payload = {
      amino_acid_seq: document.getElementById("amino_acid_seq").value.trim(),
      smile: seedSmileInput.value.trim(),
      noise: parseFloat(noiseInput.value),
      num_candidates: parseInt(document.getElementById("num_candidates").value),
    };
    const data = await apiFetch("/api/v2/generate", { method: "POST", body: JSON.stringify(payload) });
    experimentIdInput.value = data.experiment_id;
    renderResults(data);
    resultsSection.style.display = "block";
    document.getElementById("save-panel").style.display = "block";
  } catch (err) {
    showAlert(err.message || "Generation failed", "error", form.closest(".card"));
  } finally {
    setLoading(btn, false);
  }
});

function renderResults(data) {
  const { candidates, seed_properties: sp, meta } = data;
  document.getElementById("meta-info").textContent =
    `Generated ${meta.generated} valid candidates · Gemma4 latency: ${meta.gemma4_latency_ms}ms`;

  if (sp) {
    document.getElementById("seed-qed").textContent = sp.qed?.toFixed(3) ?? "-";
    document.getElementById("seed-sas").textContent = sp.sas?.toFixed(2) ?? "-";
    document.getElementById("seed-logp").textContent = sp.logp?.toFixed(2) ?? "-";
    document.getElementById("seed-mw").textContent = sp.mw?.toFixed(1) ?? "-";
  }

  resultsBody.innerHTML = "";
  candidates.forEach(c => {
    const tr = document.createElement("tr");
    if (c.rank === 1) tr.className = "rank-1";
    tr.innerHTML = `
      <td>${c.rank}</td>
      <td class="smiles-cell" title="${c.smiles}">${c.smiles}</td>
      <td>${(c.composite_score ?? 0).toFixed(3)}</td>
      <td>${(c.dti_score ?? 0).toFixed(3)}</td>
      <td>${(c.qed ?? 0).toFixed(3)}</td>
      <td>${(c.sas ?? 0).toFixed(2)}</td>
      <td>${(c.logp ?? 0).toFixed(2)}</td>
      <td>${(c.mw ?? 0).toFixed(1)}</td>
      <td>${(c.tanimoto ?? 0).toFixed(3)}</td>
      <td class="${c.lipinski_pass ? 'pass' : 'fail'}">${c.lipinski_pass ? "✓" : "✗"}</td>
      <td>
        <button class="btn btn-sm btn-outline" onclick="showMol('${c.smiles}')">View</button>
        <button class="btn btn-sm btn-outline" onclick="copySmiles('${c.smiles}')">Copy</button>
      </td>`;
    resultsBody.appendChild(tr);
  });
}

// Publish
publishBtn?.addEventListener("click", async () => {
  const expId = experimentIdInput.value;
  if (!expId) return;
  const title = titleInput.value.trim();
  if (!title) { alert("Please add a title before publishing."); return; }

  // Save title/hypothesis first
  await apiFetch(`/api/v2/experiments/${expId}`, {
    method: "PATCH",
    body: JSON.stringify({ title, hypothesis: hypothesisInput.value.trim() }),
  }).catch(() => {});

  try {
    await apiFetch(`/api/v2/experiments/${expId}/publish`, { method: "POST" });
    showAlert("Experiment published to the class feed!", "success", document.body);
    publishBtn.textContent = "Published ✓";
    publishBtn.disabled = true;
  } catch (err) {
    showAlert(err.message || "Publish failed", "error", document.body);
  }
});

// AI metadata suggestion
const aiSuggestBtn = document.getElementById("ai-suggest-btn");
const aiSuggestionBox = document.getElementById("ai-suggestion-box");
const aiAcceptBtn = document.getElementById("ai-accept-btn");
const aiRetryBtn = document.getElementById("ai-retry-btn");
const aiDismissBtn = document.getElementById("ai-dismiss-btn");

let lastSuggestion = null;

async function suggestMetadata() {
  const expId = experimentIdInput.value;
  if (!expId) return;

  aiSuggestBtn.classList.add("loading");
  aiSuggestBtn.disabled = true;
  document.getElementById("ai-suggest-label").textContent = "Thinking…";
  aiSuggestionBox.style.display = "none";

  try {
    const data = await apiFetch("/api/v2/suggest-metadata", {
      method: "POST",
      body: JSON.stringify({ experiment_id: expId }),
    });
    lastSuggestion = data;
    document.getElementById("ai-sug-title").textContent = data.title;
    document.getElementById("ai-sug-hypothesis").textContent = data.hypothesis;
    aiSuggestionBox.style.display = "block";
  } catch (err) {
    showAlert(err.message || "AI suggestion failed", "error", document.body);
  } finally {
    aiSuggestBtn.classList.remove("loading");
    aiSuggestBtn.disabled = false;
    document.getElementById("ai-suggest-label").textContent = "AI Suggest";
  }
}

aiSuggestBtn?.addEventListener("click", suggestMetadata);
aiRetryBtn?.addEventListener("click", suggestMetadata);

aiAcceptBtn?.addEventListener("click", () => {
  if (!lastSuggestion) return;
  titleInput.value = lastSuggestion.title;
  hypothesisInput.value = lastSuggestion.hypothesis;
  aiSuggestionBox.style.display = "none";
});

aiDismissBtn?.addEventListener("click", () => {
  aiSuggestionBox.style.display = "none";
});

// Molecule viewer modal
function showMol(smiles) {
  const modal = document.getElementById("mol-modal");
  const img = document.getElementById("mol-modal-img");
  const smilesEl = document.getElementById("mol-modal-smiles");
  img.src = molSvgUrl(smiles);
  smilesEl.textContent = smiles;
  modal.style.display = "flex";
}
document.getElementById("mol-modal-close")?.addEventListener("click", () => {
  document.getElementById("mol-modal").style.display = "none";
});

function copySmiles(smiles) {
  navigator.clipboard.writeText(smiles).then(() => showAlert("SMILES copied to clipboard", "success", document.body));
}
