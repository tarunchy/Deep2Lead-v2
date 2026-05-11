const BLOB_COLORS = ['c1','c2','c3','c4','c5','c6','c7'];
let currentAudio = null;
let overlayBossId = null;

function initSelector() {
    const grid = document.getElementById('bossSelectorGrid');
    if (!grid || !window.BOSSES_JSON) return;

    window.BOSSES_JSON.forEach((boss, idx) => {
        const locked = boss.game_level > 2;
        const blobClass = 'boss-blob-' + (BLOB_COLORS[idx % BLOB_COLORS.length]);
        const diffLabel = boss.game_level <= 2 ? 'Scientist Junior' :
                          boss.game_level <= 4 ? 'Research Fellow' :
                          boss.game_level <= 6 ? 'Principal Investigator' : 'Nobel Prize';
        const diffCls = boss.game_level <= 2 ? 'boss-diff-junior' :
                        boss.game_level <= 4 ? 'boss-diff-fellow' :
                        boss.game_level <= 6 ? 'boss-diff-pi' : 'boss-diff-nobel';

        const card = document.createElement('div');
        card.className = 'boss-select-card' + (locked ? ' locked-card' : '');
        card.setAttribute('data-idx', idx);
        card.innerHTML = `
            <div class="boss-blob-wrap">
                <div class="boss-blob ${blobClass}">${boss.game_emoji || '🦠'}</div>
                ${locked ? '<div class="lock-overlay-badge">🔒</div>' : ''}
            </div>
            <div class="boss-card-info">
                <div class="boss-card-name">${boss.game_name || boss.id}</div>
                <div style="margin-top:6px;">
                    <span class="boss-level-pill">LVL ${boss.game_level}</span>
                    <span class="boss-diff-pill ${diffCls}">${diffLabel}</span>
                </div>
            </div>
        `;

        card.style.animationDelay = (idx * 0.08) + 's';

        if (!locked) {
            card.addEventListener('click', () => openBossOverlay(boss));
        }
        grid.appendChild(card);
    });

    initBlobAnimations();
}

function openBossOverlay(boss) {
    overlayBossId = boss.target_id || boss.id;
    const overlay = document.getElementById('bossIntroOverlay');
    const panel = document.getElementById('bossIntroPanel');
    if (!overlay) return;

    const knownPct = Math.round((boss.known_drug_score || 0.60) * 100);
    const winPct = Math.round((boss.win_threshold_easy || 0.70) * 100);

    panel.innerHTML = `
        <span class="boss-intro-emoji">${boss.game_emoji || '🦠'}</span>
        <div class="boss-intro-name">${boss.game_name || boss.id}</div>
        <div class="boss-intro-disease">${boss.disease || ''} · ${boss.short_name || ''}</div>
        <div class="boss-intro-lore">${boss.game_intro || boss.plain_english || 'A dangerous pathogen awaits. Design molecules to defeat it.'}</div>
        <div class="boss-intro-stats">
            <div class="boss-stat">
                <span class="boss-stat-val">${knownPct}%</span>
                <span class="boss-stat-label">Known Drug Score</span>
            </div>
            <div class="boss-stat">
                <span class="boss-stat-val">${winPct}%</span>
                <span class="boss-stat-label">Win Threshold</span>
            </div>
            <div class="boss-stat">
                <span class="boss-stat-val">LVL ${boss.game_level}</span>
                <span class="boss-stat-label">Difficulty</span>
            </div>
        </div>
        <div class="boss-intro-btns">
            <button class="intro-cancel-btn" id="overlayCancel">Cancel</button>
            <button class="enter-battle-btn" id="overlayEnter">⚔️ ENTER BATTLE</button>
        </div>
    `;

    overlay.style.display = 'flex';

    document.getElementById('overlayEnter').addEventListener('click', () => {
        stopTTS();
        window.location.href = '/game/pathohunt-3d/' + overlayBossId;
    });
    document.getElementById('overlayCancel').addEventListener('click', closeOverlay);

    const introText = boss.game_intro || boss.plain_english || '';
    if (introText) {
        playBossIntro(introText.substring(0, 300));
    }
}

function closeOverlay() {
    const overlay = document.getElementById('bossIntroOverlay');
    if (overlay) overlay.style.display = 'none';
    stopTTS();
    overlayBossId = null;
}

function stopTTS() {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
}

async function playBossIntro(text) {
    stopTTS();
    try {
        const resp = await fetch('/api/v3/game/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        const blob = await resp.blob();
        const audio = new Audio(URL.createObjectURL(blob));
        currentAudio = audio;
        audio.play().catch(() => {});
        audio.onended = () => { currentAudio = null; };
    } catch (e) {}
}

function initBlobAnimations() {
    document.querySelectorAll('.boss-blob').forEach((blob, i) => {
        blob.style.animationDelay = (i * 0.6) + 's';
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initSelector();

    const overlay = document.getElementById('bossIntroOverlay');
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeOverlay();
        });
    }
});
