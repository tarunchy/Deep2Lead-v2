/* Dashboard: checkbox selection, single delete, bulk delete */
(function () {
  "use strict";

  // Track checked ids per tab
  const _selected = { drafts: new Set(), published: new Set() };

  function activeTab() {
    return document.getElementById("tab-drafts").style.display !== "none" ? "drafts" : "published";
  }

  // Called by checkbox change
  window.onCardCheck = function (cb, id) {
    const tab = cb.closest("[data-tab]").dataset.tab;
    const card = cb.closest(".exp-card");
    if (cb.checked) {
      _selected[tab].add(id);
      card.classList.add("selected");
    } else {
      _selected[tab].delete(id);
      card.classList.remove("selected");
    }
    syncToolbar(tab);
  };

  window.onSelectAll = function (masterCb, tab) {
    const container = document.getElementById("tab-" + tab);
    container.querySelectorAll(".exp-card-check").forEach(cb => {
      cb.checked = masterCb.checked;
      const id = cb.dataset.id;
      if (masterCb.checked) {
        _selected[tab].add(id);
        cb.closest(".exp-card").classList.add("selected");
      } else {
        _selected[tab].delete(id);
        cb.closest(".exp-card").classList.remove("selected");
      }
    });
    syncToolbar(tab);
  };

  function syncToolbar(tab) {
    const count = _selected[tab].size;
    const toolbar = document.getElementById("bulk-toolbar-" + tab);
    const countEl = document.getElementById("sel-count-" + tab);
    if (!toolbar) return;
    toolbar.classList.toggle("visible", count > 0);
    if (countEl) countEl.textContent = count + " selected";
  }

  // Single delete
  window.deleteSingle = function (id, title) {
    showConfirm(
      `Delete "${title || "Untitled"}"?`,
      "This cannot be undone. The experiment and all its candidates will be permanently removed.",
      async () => {
        const res = await apiFetch(`/api/v2/experiments/${id}`, { method: "DELETE" });
        if (res.deleted) {
          const card = document.querySelector(`[data-exp-id="${id}"]`);
          if (card) card.remove();
          // Remove from selection sets
          Object.values(_selected).forEach(s => s.delete(id));
          updateEmptyStates();
        } else {
          showAlert(res.error || "Delete failed", "error");
        }
      }
    );
  };

  // Bulk delete
  window.bulkDelete = function (tab) {
    const ids = Array.from(_selected[tab]);
    if (!ids.length) return;
    showConfirm(
      `Delete ${ids.length} experiment${ids.length > 1 ? "s" : ""}?`,
      "This cannot be undone. All selected experiments and their candidates will be permanently removed.",
      async () => {
        const res = await apiFetch("/api/v2/experiments/bulk-delete", {
          method: "POST",
          body: JSON.stringify({ ids }),
        });
        if (res.deleted) {
          res.deleted.forEach(id => {
            const card = document.querySelector(`[data-exp-id="${id}"]`);
            if (card) card.remove();
            _selected[tab].delete(id);
          });
          syncToolbar(tab);
          // Uncheck master checkbox
          const master = document.getElementById("select-all-" + tab);
          if (master) master.checked = false;
          updateEmptyStates();
          showAlert(`Deleted ${res.count} experiment${res.count > 1 ? "s" : ""}.`, "success");
        } else {
          showAlert(res.error || "Bulk delete failed", "error");
        }
      }
    );
  };

  function updateEmptyStates() {
    ["drafts", "published"].forEach(tab => {
      const container = document.getElementById("tab-" + tab);
      if (!container) return;
      const cards = container.querySelectorAll(".exp-card");
      const empty = container.querySelector(".empty-state");
      if (empty) empty.style.display = cards.length ? "none" : "block";
    });
  }

  // Confirm modal
  function showConfirm(title, body, onConfirm) {
    const overlay = document.createElement("div");
    overlay.className = "del-modal-overlay";
    overlay.innerHTML = `
      <div class="del-modal">
        <h3>${title}</h3>
        <p>${body}</p>
        <div class="del-modal-btns">
          <button class="btn btn-outline" id="_cancelDel">Cancel</button>
          <button class="btn" style="background:#da3633;color:#fff;border:none;" id="_confirmDel">Delete</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector("#_cancelDel").onclick = () => overlay.remove();
    overlay.querySelector("#_confirmDel").onclick = async () => {
      overlay.remove();
      await onConfirm();
    };
  }
})();
