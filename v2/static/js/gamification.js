/* Gamification: XP bar updates, badge toasts, mission progress */
(function () {
  "use strict";

  async function refreshXP() {
    try {
      const data = await apiFetch("/api/v3/me/xp");
      updateXPBar(data);
    } catch (e) { /* silently ignore */ }
  }

  function updateXPBar(data) {
    const inner = document.getElementById("xpBarInner");
    const lvlBadge = document.getElementById("xpLevelBadge");
    const xpText = document.getElementById("xpText");
    if (inner) inner.style.width = (data.level_progress_pct || 0) + "%";
    if (lvlBadge) lvlBadge.textContent = `Lv ${data.level}`;
    if (xpText) xpText.textContent = `${data.total_xp} XP`;
  }

  window.showBadgeToast = function (icon, name, description) {
    const container = document.getElementById("badgeToastContainer") || document.body;
    const toast = document.createElement("div");
    toast.className = "badge-toast";
    toast.innerHTML = `
      <div class="badge-toast-icon">${icon}</div>
      <div class="badge-toast-body">
        <strong>Badge Earned: ${name}</strong>
        <span>${description}</span>
      </div>`;
    container.appendChild(toast);
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, 5000);
  };

  window.updateBossBar = function (scoreNorm) {
    // scoreNorm: 0→1 where 1 = full damage to boss
    const fill = document.getElementById("bossBarFill");
    const hpLabel = document.getElementById("bossHpLabel");
    if (!fill) return;
    const hp = Math.max(0, Math.round((1 - scoreNorm) * 100));
    fill.style.width = hp + "%";
    if (hpLabel) hpLabel.textContent = `Simulation Health: ${hp}%`;
  };

  // Refresh XP bar on every page load
  document.addEventListener("DOMContentLoaded", refreshXP);
})();
