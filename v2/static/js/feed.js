let currentPage = 1;
let currentSort = "newest";

async function loadFeed(page = 1, sort = currentSort) {
  currentPage = page;
  currentSort = sort;
  const grid = document.getElementById("feed-grid");
  grid.innerHTML = '<div class="loading-wrap"><div class="spinner"></div><span>Loading experiments…</span></div>';

  try {
    const data = await apiFetch(`/api/v2/feed?page=${page}&per_page=12&sort=${sort}`);
    renderFeed(data);
  } catch (err) {
    grid.innerHTML = `<div class="empty-state"><p>${err.message}</p></div>`;
  }
}

function renderFeed(data) {
  const grid = document.getElementById("feed-grid");
  const pagination = document.getElementById("pagination");
  grid.innerHTML = "";

  if (!data.items.length) {
    grid.innerHTML = '<div class="empty-state"><strong>No experiments yet.</strong><p>Be the first to publish!</p></div>';
    return;
  }

  data.items.forEach(exp => {
    const card = document.createElement("div");
    card.className = "exp-card";
    const top = exp.top_candidate;
    card.innerHTML = `
      <div class="exp-card-meta">${exp.author} · ${exp.cohort ?? ""} · ${formatDate(exp.published_at)}</div>
      <div class="exp-card-title">${escHtml(exp.title || "Untitled Experiment")}</div>
      <div class="text-sm text-muted">Seed:</div>
      <div class="exp-card-smiles" title="${exp.seed_smile}">${exp.seed_smile}</div>
      ${top ? `<div class="text-sm text-muted">Top candidate:</div>
      <div class="exp-card-smiles" title="${top.smiles}">${top.smiles}</div>
      <div class="exp-card-scores">
        <span class="score-badge dti">DTI ${top.dti_score?.toFixed(2)}</span>
        <span class="score-badge">QED ${top.qed?.toFixed(2)}</span>
        <span class="score-badge sas">SAS ${top.sas?.toFixed(1)}</span>
      </div>` : ""}
      <div class="exp-card-actions">
        <button class="like-btn ${exp.liked_by_me ? 'liked' : ''}" data-id="${exp.id}" data-liked="${exp.liked_by_me}">
          <span class="heart"></span> <span class="like-count">${exp.like_count}</span>
        </button>
        <span class="text-muted text-sm">💬 ${exp.comment_count}</span>
        <a href="/experiments/${exp.id}" class="btn btn-sm btn-outline" style="margin-left:auto">View</a>
      </div>`;
    card.querySelector(".exp-card-title, .exp-card-smiles").addEventListener("click", () => {
      location.href = `/experiments/${exp.id}`;
    });
    card.querySelector(".like-btn").addEventListener("click", (e) => { e.stopPropagation(); toggleLike(e.currentTarget); });
    grid.appendChild(card);
  });

  // Pagination
  pagination.innerHTML = "";
  for (let i = 1; i <= data.pages; i++) {
    const btn = document.createElement("button");
    btn.className = `btn btn-sm ${i === currentPage ? 'btn-primary' : 'btn-outline'}`;
    btn.textContent = i;
    btn.addEventListener("click", () => loadFeed(i));
    pagination.appendChild(btn);
  }
}

async function toggleLike(btn) {
  const expId = btn.dataset.id;
  try {
    const res = await apiFetch(`/api/v2/experiments/${expId}/like`, { method: "POST" });
    btn.dataset.liked = res.liked;
    btn.classList.toggle("liked", res.liked);
    btn.querySelector(".like-count").textContent = res.like_count;
  } catch (err) {
    showAlert(err.message, "error", document.body);
  }
}

function escHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Sort controls
document.querySelectorAll("[data-sort]").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("[data-sort]").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    loadFeed(1, btn.dataset.sort);
  });
});

loadFeed();
