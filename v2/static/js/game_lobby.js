/* PathoHunt lobby logic */
(function () {
  // Load user's battle history to show best scores per boss
  async function loadHistory() {
    try {
      const res = await fetch('/api/v3/game/history');
      if (!res.ok) return;
      const history = await res.json();
      const bestByTarget = {};
      for (const s of history) {
        if (!bestByTarget[s.target_id] || s.best_score > bestByTarget[s.target_id].best_score) {
          bestByTarget[s.target_id] = s;
        }
      }
      for (const [tid, s] of Object.entries(bestByTarget)) {
        const el = document.getElementById('bestScore_' + tid);
        if (el) {
          el.style.display = 'block';
          if (s.status === 'won') {
            el.textContent = '✅ Beaten! Best: ' + (s.best_score * 100).toFixed(0) + '%';
            const card = el.closest('.boss-card');
            if (card) card.classList.add('beaten');
          } else {
            el.textContent = 'Best: ' + (s.best_score * 100).toFixed(0) + '% (in progress)';
          }
        }
      }
    } catch (e) {
      // silent
    }
  }

  loadHistory();
})();
