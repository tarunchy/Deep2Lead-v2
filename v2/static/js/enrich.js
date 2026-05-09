// Lazy enrichment panel — called once when user expands the section
let _enrichLoaded = false;
const _enrichExpId = document.getElementById("experiment-data")?.dataset?.id;

function toggleEnrich() {
  const body = document.getElementById("enrich-body");
  const icon = document.getElementById("enrich-toggle-icon");
  const isOpen = body.style.display !== "none";
  body.style.display = isOpen ? "none" : "block";
  icon.textContent = isOpen ? "▲ Hide" : "▼ Load from ChEMBL & PubChem";
  if (!isOpen && !_enrichLoaded) loadEnrichment();
}

async function loadEnrichment() {
  _enrichLoaded = true;
  const content = document.getElementById("enrich-content");
  content.innerHTML = '<p class="text-muted text-sm">Querying ChEMBL and PubChem…</p>';

  try {
    const data = await apiFetch(`/api/v2/enrich/${_enrichExpId}`);
    renderEnrichment(data, content);
  } catch (err) {
    content.innerHTML = `<p class="text-muted text-sm enrich-error">Could not load enrichment data: ${err.message}</p>`;
  }
}

function renderEnrichment(data, container) {
  container.innerHTML = "";

  // External links row
  const links = data.external_links || {};
  const linkBar = document.createElement("div");
  linkBar.className = "enrich-link-bar";
  linkBar.innerHTML = `
    <a href="${links.pubchem_browse}" target="_blank" rel="noopener" class="enrich-ext-link">PubChem ↗</a>
    <a href="${links.chembl_browse}" target="_blank" rel="noopener" class="enrich-ext-link">ChEMBL ↗</a>
    <a href="${links.uniprot_blast}" target="_blank" rel="noopener" class="enrich-ext-link">UniProt BLAST ↗</a>`;
  container.appendChild(linkBar);

  // Two-column grid
  const grid = document.createElement("div");
  grid.className = "enrich-grid";

  grid.appendChild(_buildPanel("PubChem Similar Compounds", _renderPubchem(data.pubchem)));
  grid.appendChild(_buildPanel("ChEMBL Bioactivity Hits", _renderChembl(data.chembl)));

  container.appendChild(grid);
}

function _buildPanel(title, inner) {
  const card = document.createElement("div");
  card.className = "enrich-panel";
  card.innerHTML = `<p class="enrich-panel-title">${title}</p>`;
  card.appendChild(inner);
  return card;
}

function _renderPubchem(pc) {
  const wrap = document.createElement("div");
  if (pc.error) {
    wrap.innerHTML = `<p class="enrich-error">${pc.error}</p>`;
    return wrap;
  }
  if (!pc.hits || !pc.hits.length) {
    wrap.innerHTML = '<p class="text-muted text-sm">No similar compounds found (≥80% similarity).</p>';
    return wrap;
  }
  const rows = pc.hits.map(h => `
    <tr>
      <td><a href="${h.url}" target="_blank" rel="noopener">CID ${h.cid}</a></td>
      <td class="enrich-name" title="${h.name}">${h.name.length > 30 ? h.name.slice(0, 30) + "…" : h.name}</td>
      <td>${h.mw ? parseFloat(h.mw).toFixed(1) : "—"}</td>
    </tr>`).join("");
  wrap.innerHTML = `
    <table class="enrich-table">
      <thead><tr><th>CID</th><th>Name</th><th>MW</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  return wrap;
}

function _renderChembl(ch) {
  const wrap = document.createElement("div");
  if (ch.error) {
    wrap.innerHTML = `<p class="enrich-error">${ch.error}</p>`;
    return wrap;
  }
  if (!ch.hits || !ch.hits.length) {
    wrap.innerHTML = '<p class="text-muted text-sm">No similar compounds found (≥70% similarity).</p>';
    return wrap;
  }
  const phaseLabel = p => {
    if (p === null || p === undefined) return "—";
    if (p === 0) return "Pre-clinical";
    return `Phase ${p}${p === 4 ? " (Approved)" : ""}`;
  };
  const rows = ch.hits.map(h => `
    <tr>
      <td><a href="${h.url}" target="_blank" rel="noopener">${h.chembl_id}</a></td>
      <td class="enrich-name" title="${h.name}">${(h.name || "").length > 25 ? (h.name || "").slice(0, 25) + "…" : h.name || "—"}</td>
      <td>${h.similarity}%</td>
      <td class="${h.max_phase >= 4 ? 'enrich-approved' : ''}">${phaseLabel(h.max_phase)}</td>
    </tr>`).join("");
  wrap.innerHTML = `
    <table class="enrich-table">
      <thead><tr><th>ChEMBL ID</th><th>Name</th><th>Sim.</th><th>Phase</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  return wrap;
}
