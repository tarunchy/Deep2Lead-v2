/* Target picker: curated library + live search */
(function () {
  "use strict";

  let allTargets = [];
  let selected = null;
  const CATEGORY_ICONS = { viral: "🦠", cancer: "🔬", aging: "⏳", neurological: "🧠", inflammation: "🔥", antibiotic: "💊", cardiovascular: "❤️" };
  const CATEGORY_LABELS = { viral: "Viral / Pathogen", cancer: "Cancer", aging: "Aging & Longevity", neurological: "Neurological", inflammation: "Inflammation", antibiotic: "Antibiotic", cardiovascular: "Cardiovascular" };

  async function loadCurated() {
    const res = await apiFetch("/api/v3/targets/curated");
    if (res.targets) {
      allTargets = res.targets;
      renderGrid(allTargets);
      buildCategoryTabs(res.grouped);
    }
  }

  function buildCategoryTabs(grouped) {
    const bar = document.getElementById("categoryTabs");
    if (!bar) return;
    let html = `<button class="cat-tab active" data-cat="all">All (${allTargets.length})</button>`;
    for (const [cat, items] of Object.entries(grouped)) {
      html += `<button class="cat-tab" data-cat="${cat}">${CATEGORY_ICONS[cat] || ""} ${CATEGORY_LABELS[cat] || cat} (${items.length})</button>`;
    }
    bar.innerHTML = html;
    bar.querySelectorAll(".cat-tab").forEach(btn => {
      btn.addEventListener("click", () => {
        bar.querySelectorAll(".cat-tab").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const cat = btn.dataset.cat;
        renderGrid(cat === "all" ? allTargets : allTargets.filter(t => t.category === cat));
      });
    });
  }

  function renderGrid(targets) {
    const grid = document.getElementById("targetGrid");
    if (!grid) return;
    if (!targets.length) {
      grid.innerHTML = `<div style="color:#8b949e;padding:20px;">No targets found.</div>`;
      return;
    }
    grid.innerHTML = targets.map(t => `
      <div class="target-card" data-id="${t.id}" onclick="selectTarget(${JSON.stringify(t).replace(/"/g, '&quot;')})">
        <div class="target-card-header">
          <div class="target-icon">${CATEGORY_ICONS[t.category] || "🎯"}</div>
          <div>
            <span class="difficulty-pill difficulty-${t.difficulty}">${t.difficulty}</span>
            <div class="target-card-name">${t.name}</div>
            <div class="target-card-disease">${t.disease} · ${t.organism}</div>
          </div>
        </div>
        <div class="target-card-desc">${t.description}</div>
        <div class="target-badges">
          <span class="target-badge ${t.category}">${t.category}</span>
          ${t.pdb_id ? `<span class="target-badge">PDB: ${t.pdb_id}</span>` : ""}
          ${t.alphafold_available ? `<span class="target-badge">AlphaFold ✓</span>` : ""}
        </div>
      </div>
    `).join("");
  }

  window.selectTarget = function (target) {
    selected = target;
    document.querySelectorAll(".target-card").forEach(c => c.classList.remove("selected"));
    const card = document.querySelector(`.target-card[data-id="${target.id}"]`);
    if (card) card.classList.add("selected");

    const panel = document.getElementById("targetDetail");
    if (panel) {
      panel.innerHTML = `
        <h3>${CATEGORY_ICONS[target.category] || "🎯"} ${target.name}</h3>
        <p style="color:#8b949e;font-size:.9rem;">${target.description}</p>
        <div class="struct-info">
          <div class="struct-info-item"><div class="si-label">Organism</div><div class="si-val">${target.organism}</div></div>
          <div class="struct-info-item"><div class="si-label">Disease</div><div class="si-val">${target.disease}</div></div>
          <div class="struct-info-item"><div class="si-label">PDB</div><div class="si-val">${target.pdb_id || "—"}</div></div>
          <div class="struct-info-item"><div class="si-label">UniProt</div><div class="si-val">${target.uniprot_id || "—"}</div></div>
        </div>
        <div style="background:rgba(88,166,255,.08);border:1px solid rgba(88,166,255,.2);border-radius:8px;padding:12px;margin:10px 0;font-size:.85rem;">
          <strong>🔑 Analogy:</strong> ${target.analogy}
        </div>
        <p style="font-size:.83rem;color:#8b949e;margin-top:8px;">
          Known drug: <strong style="color:#e6edf3;">${target.known_drug}</strong>
        </p>`;
      panel.style.display = "block";
    }

    // Fill hidden fields if inside run_3d form
    const fTargetId = document.getElementById("f_target_id");
    const fTargetName = document.getElementById("f_target_name");
    const fUniprotId = document.getElementById("f_uniprot_id");
    const fPdbId = document.getElementById("f_pdb_id");
    const fSeedSmiles = document.getElementById("seed_smiles");
    if (fTargetId) fTargetId.value = target.id;
    if (fTargetName) fTargetName.value = target.name;
    if (fUniprotId) fUniprotId.value = target.uniprot_id || "";
    if (fPdbId) fPdbId.value = target.pdb_id || "";
    if (fSeedSmiles && !fSeedSmiles.value) fSeedSmiles.value = target.known_drug_smiles || target.starter_smiles || "";

    const btn = document.getElementById("continueBtn");
    if (btn) btn.disabled = false;

    // Dispatch custom event for parent pages to react
    window.dispatchEvent(new CustomEvent("targetSelected", { detail: target }));
  };

  // Live search
  const searchInput = document.getElementById("targetSearch");
  const searchBtn = document.getElementById("targetSearchBtn");
  async function doSearch() {
    const q = searchInput ? searchInput.value.trim() : "";
    if (q.length < 2) { renderGrid(allTargets); return; }
    const grid = document.getElementById("targetGrid");
    if (grid) grid.innerHTML = `<div style="color:#8b949e;padding:20px;">Searching…</div>`;
    const res = await apiFetch(`/api/v3/targets/search?q=${encodeURIComponent(q)}`);
    const combined = [...(res.curated || []), ...(res.uniprot || []).map(u => ({
      id: u.uniprot_id, name: u.protein_name || u.gene, disease: u.organism, organism: u.organism,
      category: "unknown", description: `UniProt: ${u.uniprot_id}`, uniprot_id: u.uniprot_id,
      difficulty: "unknown", alphafold_available: false, tags: [],
    }))];
    renderGrid(combined);
  }
  if (searchBtn) searchBtn.addEventListener("click", doSearch);
  if (searchInput) searchInput.addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });

  document.addEventListener("DOMContentLoaded", loadCurated);
})();
