let currentRp = 0;

async function loadRp() {
  const res = await fetch("/api/v3/game/rp");
  if (!res.ok) return;
  const data = await res.json();
  currentRp = data.rp || 0;
  document.getElementById("rpBalance").textContent = currentRp + " RP";
}

async function loadUpgrades() {
  const res = await fetch("/api/v3/game/upgrades");
  if (!res.ok) {
    document.getElementById("upgradeGrid").innerHTML = "<p>Failed to load upgrades.</p>";
    return;
  }
  const upgrades = await res.json();
  renderUpgrades(upgrades);
}

function renderUpgrades(upgrades) {
  const grid = document.getElementById("upgradeGrid");
  if (!upgrades.length) {
    grid.innerHTML = "<p class='lab-loading'>No upgrades available yet.</p>";
    return;
  }
  grid.innerHTML = upgrades.map(up => `
    <div class="upgrade-card ${up.owned ? 'owned' : ''}" data-slug="${up.slug}">
      <div class="upgrade-icon">${up.icon}</div>
      <div class="upgrade-name">${up.name}</div>
      <div class="upgrade-desc">${up.description}</div>
      <div class="upgrade-cost">${up.owned ? "Owned" : up.cost_rp + " RP"}</div>
      ${up.owned
        ? `<button class="upgrade-btn owned-badge" disabled>Activated</button>`
        : `<button class="upgrade-btn" data-slug="${up.slug}" data-cost="${up.cost_rp}"
             ${currentRp < up.cost_rp ? "disabled" : ""}>
             Purchase
           </button>`
      }
    </div>
  `).join("");

  grid.querySelectorAll(".upgrade-btn:not(.owned-badge)").forEach(btn => {
    btn.addEventListener("click", () => purchaseUpgrade(btn.dataset.slug, parseInt(btn.dataset.cost)));
  });
}

async function purchaseUpgrade(slug, cost) {
  if (currentRp < cost) {
    alert(`Not enough RP. You need ${cost} RP but have ${currentRp}.`);
    return;
  }
  const res = await fetch("/api/v3/game/upgrade/purchase", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({slug}),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.error || "Purchase failed");
    return;
  }
  await loadRp();
  await loadUpgrades();
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadRp();
  await loadUpgrades();
});
