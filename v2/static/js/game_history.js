/* ── Game History page ──────────────────────────────────────────────── */

let allSessions = [];
let currentFilter = 'all';

const STATUS_LABELS = {
    won: '⚡ Won', lost: '💀 Lost', abandoned: '🚪 Abandoned', active: '⏳ Active'
};

function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
        + ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function fmtDuration(s) {
    if (!s) return '—';
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60), sec = s % 60;
    return sec ? `${m}m ${sec}s` : `${m}m`;
}

function scoreClass(v) {
    if (v >= 0.65) return 'good';
    if (v >= 0.45) return 'ok';
    return 'bad';
}

function renderStats(sessions) {
    const total  = sessions.length;
    const won    = sessions.filter(s => s.status === 'won').length;
    const attacks = sessions.reduce((a, s) => a + (s.attacks_count || 0), 0);
    const best   = sessions.reduce((b, s) => Math.max(b, s.best_score || 0), 0);

    document.getElementById('statTotal').textContent   = total;
    document.getElementById('statWon').textContent     = won;
    document.getElementById('statAttacks').textContent = attacks;
    document.getElementById('statBestScore').textContent = best ? `${Math.round(best * 100)}%` : '—';
}

function buildCard(s) {
    const best    = s.best_attack;
    const score   = best ? best.composite_score : null;
    const smiles  = best ? best.smiles : null;
    const pct     = score !== null ? Math.round(score * 100) : null;
    const scoreHtml = pct !== null
        ? `<span class="gh-mol-score ${scoreClass(score)}">${pct}%</span>`
        : '';

    const molHtml = smiles ? `
        <div class="gh-best-mol">
            <span class="gh-mol-label">Best Mol</span>
            <span class="gh-mol-smiles" title="${smiles}">${smiles}</span>
            ${scoreHtml}
        </div>` : '';

    const hpPct = s.boss_initial_hp
        ? Math.round(((s.boss_initial_hp - Math.max(0, s.boss_current_hp)) / s.boss_initial_hp) * 100)
        : 0;

    const card = document.createElement('div');
    card.className = `gh-session-card status-${s.status}`;
    card.dataset.sessionId = s.id;
    card.dataset.status = s.status;

    card.innerHTML = `
        <div class="gh-boss-icon">${s.boss_emoji || '🦠'}</div>
        <div class="gh-session-info">
            <div class="gh-session-top">
                <span class="gh-boss-name">${s.boss_name}</span>
                <span class="gh-status-badge ${s.status}">${STATUS_LABELS[s.status] || s.status}</span>
            </div>
            <div class="gh-session-meta">
                <span class="gh-meta-item">⚔️ <strong>${s.attacks_count || 0}</strong> attacks</span>
                <span class="gh-meta-item">💥 <strong>${hpPct}%</strong> boss HP drained</span>
                <span class="gh-meta-item">⏱ <strong>${fmtDuration(s.duration_s)}</strong></span>
                <span class="gh-meta-item">🎯 Mode: <strong>${s.mode}</strong></span>
            </div>
            ${molHtml}
        </div>
        <div class="gh-session-actions">
            <div class="gh-date">${fmtDate(s.time_started)}</div>
            <a href="/game/pathohunt-3d/${s.target_id}" class="gh-action-btn replay">🔁 Replay</a>
            ${smiles ? `<button class="gh-action-btn save" onclick="saveToExperiment('${s.id}', this)">📂 Save to Experiments</button>` : ''}
        </div>
    `;
    return card;
}

function applyFilter(filter) {
    currentFilter = filter;
    document.querySelectorAll('.gh-filter-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.filter === filter);
    });
    renderList();
}

function renderList() {
    const list = document.getElementById('ghSessionList');
    list.innerHTML = '';
    const filtered = currentFilter === 'all'
        ? allSessions
        : allSessions.filter(s => s.status === currentFilter);

    if (!filtered.length) {
        list.innerHTML = `<div class="gh-empty">
            <h3>No sessions found</h3>
            <p>Try a different filter or <a href="/game/pathohunt-3d">start a new battle</a>.</p>
        </div>`;
        return;
    }
    filtered.forEach(s => list.appendChild(buildCard(s)));
}

async function saveToExperiment(sessionId, btn) {
    btn.textContent = '⏳ Saving…';
    btn.className = 'gh-action-btn saving';
    btn.disabled = true;

    try {
        const resp = await fetch(`/api/v3/game/session/${sessionId}/save`, { method: 'POST' });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Save failed');

        btn.textContent = '✅ Saved';
        btn.className = 'gh-action-btn saved';

        const toast = document.getElementById('ghToast');
        toast.innerHTML = `✅ Session saved to <a href="/dashboard" style="color:#9ae6b4;text-decoration:underline;">My Experiments</a>`;
        toast.style.display = 'block';
        setTimeout(() => { toast.style.display = 'none'; }, 5000);
    } catch (e) {
        btn.textContent = '⚠ Retry';
        btn.className = 'gh-action-btn save';
        btn.disabled = false;
        alert(e.message);
    }
}

async function loadHistory() {
    try {
        const resp = await fetch('/api/v3/game/history/full');
        allSessions = await resp.json();
        renderStats(allSessions);
        renderList();
    } catch {
        document.getElementById('ghSessionList').innerHTML =
            '<div class="gh-empty"><h3>Failed to load history</h3><p>Please refresh the page.</p></div>';
    }
}

// Filter buttons
document.querySelectorAll('.gh-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => applyFilter(btn.dataset.filter));
});

loadHistory();
