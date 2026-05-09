const expId = document.getElementById("experiment-data").dataset.id;

// ── Like ────────────────────────────────────────────────────────────
const likeBtn = document.getElementById("like-btn");
likeBtn?.addEventListener("click", async () => {
  try {
    const res = await apiFetch(`/api/v2/experiments/${expId}/like`, { method: "POST" });
    likeBtn.classList.toggle("liked", res.liked);
    likeBtn.querySelector(".like-count").textContent = res.like_count;
  } catch (err) {
    showAlert(err.message, "error", document.body);
  }
});

// ── Comments ────────────────────────────────────────────────────────
async function loadComments() {
  const container = document.getElementById("comments-list");
  if (!container) return;  // not rendered for draft/retracted experiments
  try {
    const comments = await apiFetch(`/api/v2/experiments/${expId}/comments`);
    renderComments(comments, container);
  } catch (err) {
    container.innerHTML = `<p class="text-muted text-sm">${err.message}</p>`;
  }
}

function renderComments(comments, container) {
  container.innerHTML = "";
  if (!comments.length) {
    container.innerHTML = '<p class="text-muted text-sm">No comments yet. Start the discussion!</p>';
    return;
  }
  comments.forEach(c => container.appendChild(buildComment(c)));
}

function buildComment(c) {
  const div = document.createElement("div");
  div.className = "comment-item";
  div.dataset.id = c.id;
  const tagHtml = c.tag ? `<span class="comment-tag tag-${c.tag}">${c.tag}</span>` : "";
  div.innerHTML = `
    <div class="flex items-center gap-8">
      <span class="comment-author">${escHtml(c.author)}</span>
      ${tagHtml}
      <span class="comment-meta">${formatDate(c.created_at)}${c.is_edited ? " (edited)" : ""}</span>
    </div>
    <div class="comment-body">${escHtml(c.body)}</div>
    <div class="flex gap-8 mt-8">
      <button class="btn btn-sm btn-outline" onclick="startReply('${c.id}', '${escHtml(c.author)}')">Reply</button>
    </div>`;

  if (c.replies?.length) {
    const repliesDiv = document.createElement("div");
    repliesDiv.style.marginTop = "8px";
    c.replies.forEach(r => {
      const rdiv = buildComment(r);
      rdiv.classList.add("reply");
      repliesDiv.appendChild(rdiv);
    });
    div.appendChild(repliesDiv);
  }
  return div;
}

function escHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Comment form
const commentForm = document.getElementById("comment-form");
let replyTo = null;

commentForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = document.getElementById("comment-body").value.trim();
  const tag = document.getElementById("comment-tag").value || null;
  if (!body) return;

  try {
    await apiFetch(`/api/v2/experiments/${expId}/comments`, {
      method: "POST",
      body: JSON.stringify({ body, tag, parent_id: replyTo }),
    });
    document.getElementById("comment-body").value = "";
    replyTo = null;
    document.getElementById("reply-indicator").style.display = "none";
    loadComments();
  } catch (err) {
    showAlert(err.message, "error", commentForm);
  }
});

function startReply(parentId, authorName) {
  replyTo = parentId;
  const indicator = document.getElementById("reply-indicator");
  indicator.style.display = "block";
  indicator.textContent = `Replying to ${authorName} — `;
  const cancel = document.createElement("a");
  cancel.href = "#";
  cancel.textContent = "cancel";
  cancel.onclick = (e) => { e.preventDefault(); replyTo = null; indicator.style.display = "none"; };
  indicator.appendChild(cancel);
  document.getElementById("comment-body").focus();
}

// ── Candidate table ─────────────────────────────────────────────────
async function loadCandidates() {
  try {
    const data = await apiFetch(`/api/v2/experiments/${expId}`);
    renderCandidates(data.candidates || []);
  } catch (err) {
    console.error(err);
  }
}

function renderCandidates(candidates) {
  const body = document.getElementById("candidates-body");
  if (!body) return;
  body.innerHTML = "";
  candidates.forEach(c => {
    const tr = document.createElement("tr");
    if (c.rank === 1) tr.className = "rank-1";
    tr.innerHTML = `
      <td>${c.rank}</td>
      <td class="smiles-cell" title="${c.smiles}">${c.smiles}</td>
      <td>${c.composite_score?.toFixed(3) ?? "-"}</td>
      <td>${c.dti_score?.toFixed(3) ?? "-"}</td>
      <td>${c.qed?.toFixed(3) ?? "-"}</td>
      <td>${c.sas?.toFixed(2) ?? "-"}</td>
      <td>${c.logp?.toFixed(2) ?? "-"}</td>
      <td>${c.mw?.toFixed(1) ?? "-"}</td>
      <td>${c.tanimoto?.toFixed(3) ?? "-"}</td>
      <td class="${c.lipinski_pass ? 'pass' : 'fail'}">${c.lipinski_pass ? "✓" : "✗"}</td>
      <td>
        <img src="${molSvgUrl(c.smiles)}" alt="molecule" style="width:120px;height:80px;border:1px solid #e2e6ea;border-radius:4px;" onerror="this.style.display='none'">
      </td>`;
    body.appendChild(tr);
  });
}

loadComments();
loadCandidates();
