/* ── State ─────────────────────────────────────────────── */
const SCREENS = { TITLE: 'screenTitle', MENU: 'screenMenu', SELECT: 'screenSelect' };
const BLOB_COLORS = ['c1','c2','c3','c4','c5','c6','c7'];
let currentAudio = null;
let overlayBossId = null;

/* ── Canvas background ─────────────────────────────────── */
function initCanvas() {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let W, H, particles;

    function resize() {
        W = canvas.width  = window.innerWidth;
        H = canvas.height = window.innerHeight;
        particles = buildParticles();
    }

    function buildParticles() {
        const count = Math.floor((W * H) / 22000);
        return Array.from({ length: Math.min(count, 40) }, () => makeParticle());
    }

    function makeParticle() {
        const r = 6 + Math.random() * 20;
        return {
            x: Math.random() * W,
            y: Math.random() * H,
            r,
            vx: (Math.random() - 0.5) * 0.3,
            vy: (Math.random() - 0.5) * 0.3,
            spikes: 6 + Math.floor(Math.random() * 5),
            hue: Math.random() * 60 + 160,
            alpha: 0.1 + Math.random() * 0.25,
            rot: Math.random() * Math.PI * 2,
            rotSpeed: (Math.random() - 0.5) * 0.004,
        };
    }

    function drawSpike(ctx, p) {
        const inner = p.r * 0.52;
        const outer = p.r;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.beginPath();
        for (let i = 0; i < p.spikes * 2; i++) {
            const angle = (i / (p.spikes * 2)) * Math.PI * 2;
            const dist  = i % 2 === 0 ? outer : inner;
            const x = Math.cos(angle) * dist;
            const y = Math.sin(angle) * dist;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.strokeStyle = `hsla(${p.hue}, 100%, 65%, ${p.alpha})`;
        ctx.lineWidth = 0.8;
        ctx.stroke();
        ctx.fillStyle = `hsla(${p.hue}, 100%, 65%, ${p.alpha * 0.15})`;
        ctx.fill();
        ctx.restore();
    }

    function tick() {
        ctx.clearRect(0, 0, W, H);
        particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;
            p.rot += p.rotSpeed;
            if (p.x < -p.r * 2) p.x = W + p.r;
            if (p.x > W + p.r * 2) p.x = -p.r;
            if (p.y < -p.r * 2) p.y = H + p.r;
            if (p.y > H + p.r * 2) p.y = -p.r;
            drawSpike(ctx, p);
        });
        requestAnimationFrame(tick);
    }

    window.addEventListener('resize', resize);
    resize();
    tick();
}

/* ── Screen transitions ────────────────────────────────── */
function showScreen(id) {
    Object.values(SCREENS).forEach(sid => {
        const el = document.getElementById(sid);
        if (!el) return;
        el.style.display = 'none';
        el.classList.remove('gs-fade-in');
    });
    const target = document.getElementById(id);
    if (!target) return;
    target.style.display = 'flex';
    requestAnimationFrame(() => target.classList.add('gs-fade-in'));
}

/* ── Title screen ──────────────────────────────────────── */
function initTitleScreen() {
    const cta = document.getElementById('titleCta');
    if (!cta) return;

    function goToMenu() {
        showScreen(SCREENS.MENU);
        document.removeEventListener('keydown', goToMenu);
        cta.removeEventListener('click', goToMenu);
    }

    cta.addEventListener('click', goToMenu);
    document.addEventListener('keydown', goToMenu);
}

/* ── Main menu ─────────────────────────────────────────── */
function initMainMenu() {
    document.getElementById('menuSelectTarget')?.addEventListener('click', () => {
        buildDossierGrid();
        showScreen(SCREENS.SELECT);
    });

    document.getElementById('menuHowToPlay')?.addEventListener('click', () => {
        window.location.href = '/game/pathohunt-3d/tutorial';
    });

    document.getElementById('menuBattleLog')?.addEventListener('click', () => {
        window.location.href = '/profile';
    });
}

/* ── Dossier grid ──────────────────────────────────────── */
function buildDossierGrid() {
    const grid = document.getElementById('bossSelectorGrid');
    if (!grid || !window.BOSSES_JSON) return;
    if (grid.children.length > 0) return; // already built

    const total = window.BOSSES_JSON.length;
    const unlocked = window.BOSSES_JSON.filter(b => b.unlocked).length;
    const countEl = document.getElementById('selectCount');
    if (countEl) countEl.textContent = `${unlocked} / ${total} UNLOCKED`;

    window.BOSSES_JSON.forEach((boss, idx) => {
        const locked = !boss.unlocked;
        const blobCls = 'gs-blob-' + BLOB_COLORS[idx % BLOB_COLORS.length];

        const diffLabel = boss.game_level <= 2 ? 'Scientist Jr.' :
                          boss.game_level <= 4 ? 'Research Fellow' :
                          boss.game_level <= 6 ? 'Principal Investigator' : 'Nobel Prize';
        const diffCls = boss.game_level <= 2 ? 'gs-diff-junior' :
                        boss.game_level <= 4 ? 'gs-diff-fellow' :
                        boss.game_level <= 6 ? 'gs-diff-pi' : 'gs-diff-nobel';

        const card = document.createElement('div');
        card.className = 'gs-dossier' + (locked ? ' gs-locked' : '');

        card.innerHTML = `
            <div class="gs-dossier-header">
                <span>FILE #${String(idx + 1).padStart(3, '0')}</span>
                <span class="gs-dossier-status ${locked ? 'gs-status-locked' : 'gs-status-active'}">${locked ? 'CLASSIFIED' : 'ACTIVE'}</span>
            </div>
            <div class="gs-dossier-visual">
                <div class="gs-dossier-scan"></div>
                <div class="gs-dossier-blob ${blobCls}">${boss.game_emoji || '🦠'}</div>
            </div>
            <div class="gs-dossier-body">
                <div class="gs-dossier-name">${boss.game_name || boss.id}</div>
                <div class="gs-dossier-disease">${boss.disease || boss.short_name || ''}</div>
                <div class="gs-dossier-pills">
                    <span class="gs-lvl-pill">LVL ${boss.game_level}</span>
                    <span class="gs-diff-pill ${diffCls}">${diffLabel}</span>
                </div>
            </div>
            ${locked ? `
            <div class="gs-classified-overlay">
                <div class="gs-classified-stamp">CLASSIFIED</div>
                <div class="gs-classified-hint">Beat Level ${boss.game_level - 1} to unlock</div>
            </div>` : ''}
        `;

        if (!locked) {
            card.addEventListener('click', () => openBossOverlay(boss));
        }
        grid.appendChild(card);
    });

    // stagger blob animation
    grid.querySelectorAll('.gs-dossier-blob').forEach((b, i) => {
        b.style.animationDelay = (i * 0.5) + 's';
    });
}

/* ── Back button ───────────────────────────────────────── */
function initSelectBack() {
    document.getElementById('selectBack')?.addEventListener('click', () => {
        showScreen(SCREENS.MENU);
    });
}

/* ── Boss intro overlay ────────────────────────────────── */
function openBossOverlay(boss) {
    overlayBossId = boss.target_id || boss.id;
    const overlay = document.getElementById('bossIntroOverlay');
    const panel   = document.getElementById('bossIntroPanel');
    if (!overlay || !panel) return;

    const knownPct = Math.round((boss.known_drug_score || 0.60) * 100);
    const winPct   = Math.round((boss.win_threshold_easy || 0.70) * 100);

    panel.innerHTML = `
        <span class="gs-intro-emoji">${boss.game_emoji || '🦠'}</span>
        <div class="gs-intro-name">${boss.game_name || boss.id}</div>
        <div class="gs-intro-disease">${boss.disease || ''} · ${boss.short_name || ''}</div>
        <div class="gs-intro-lore">${boss.game_intro || boss.plain_english || 'A dangerous pathogen awaits. Design molecules to defeat it.'}</div>
        <div class="gs-intro-stats">
            <div class="gs-intro-stat">
                <span class="gs-intro-stat-val">${knownPct}%</span>
                <span class="gs-intro-stat-label">Known Drug Score</span>
            </div>
            <div class="gs-intro-stat">
                <span class="gs-intro-stat-val">${winPct}%</span>
                <span class="gs-intro-stat-label">Win Threshold</span>
            </div>
            <div class="gs-intro-stat">
                <span class="gs-intro-stat-val">LVL ${boss.game_level}</span>
                <span class="gs-intro-stat-label">Difficulty</span>
            </div>
        </div>
        <div class="gs-intro-btns">
            <button class="gs-cancel-btn" id="overlayCancel">Cancel</button>
            <button class="gs-enter-btn"  id="overlayEnter">⚔ ENTER BATTLE</button>
        </div>
    `;

    overlay.style.display = 'flex';

    document.getElementById('overlayEnter').addEventListener('click', () => {
        stopTTS();
        window.location.href = '/game/pathohunt-3d/' + overlayBossId;
    });
    document.getElementById('overlayCancel').addEventListener('click', closeOverlay);

    const introText = boss.game_intro || boss.plain_english || '';
    if (introText) playBossIntro(introText.substring(0, 300));
}

function closeOverlay() {
    const overlay = document.getElementById('bossIntroOverlay');
    if (overlay) overlay.style.display = 'none';
    stopTTS();
    overlayBossId = null;
}

/* ── TTS ───────────────────────────────────────────────── */
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

/* ── Init ──────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    initCanvas();
    initTitleScreen();
    initMainMenu();
    initSelectBack();

    const overlay = document.getElementById('bossIntroOverlay');
    if (overlay) {
        overlay.addEventListener('click', e => {
            if (e.target === overlay) closeOverlay();
        });
    }
});
