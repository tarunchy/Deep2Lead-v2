// Shared utilities

async function apiFetch(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || res.statusText), { status: res.status, data });
  return data;
}

function showAlert(msg, type = "error", container = document.body) {
  const el = document.createElement("div");
  el.className = `alert alert-${type}`;
  el.textContent = msg;
  container.prepend(el);
  setTimeout(() => el.remove(), 5000);
}

function setLoading(btn, loading) {
  btn.disabled = loading;
  btn._originalText = btn._originalText || btn.textContent;
  btn.textContent = loading ? "Loading…" : btn._originalText;
}

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function molSvgUrl(smiles) {
  return `/api/v2/mol/svg?smiles=${encodeURIComponent(smiles)}`;
}

// Tab switching
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const group = btn.dataset.group;
    document.querySelectorAll(`[data-group="${group}"]`).forEach(b => b.classList.remove("active"));
    document.querySelectorAll(`[data-tab="${group}"]`).forEach(t => t.style.display = "none");
    btn.classList.add("active");
    document.querySelector(`[data-tab="${group}"][data-id="${btn.dataset.target}"]`)?.style.setProperty("display", "block");
  });
});
