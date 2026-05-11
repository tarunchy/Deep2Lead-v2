const TUT_STEPS = [
    {
        id: 'overview',
        title: 'What is PathoHunt 3D?',
        category: 'MISSION OVERVIEW',
        text: 'PathoHunt 3D is a <strong>real drug-discovery game</strong>. Every boss is an actual viral or cancer protein — Flu, COVID-19, HIV, EGFR Kinase, and more. Your mission: design molecules that block the protein\'s active site. The boss starts with <strong>300 HP</strong>. Drain it to zero and you may have found a genuine drug candidate.',
        audio: 'Welcome, Scientist. PathoHunt 3D is a real drug discovery game. Every boss is an actual viral or cancer protein — Flu, COVID-19, HIV, EGFR Kinase, and more. Your mission is to design molecules that block the protein active site. The boss starts with 300 hit points. Drain it to zero and you may have found a genuine drug candidate.',
    },
    {
        id: 'briefing',
        title: 'The Mission Briefing',
        category: 'BEFORE BATTLE',
        text: 'Every battle opens with a <strong>Mission Briefing screen</strong>. It shows the boss lore, the <em>composite score target</em> you need to hit to deal maximum damage, and a quick control guide. Press <strong>START MISSION</strong> when you are ready to drop into the arena.',
        audio: 'Every battle opens with a Mission Briefing screen. It shows the boss lore, the composite score target you need to deal maximum damage, and a quick control guide. Press Start Mission when you are ready to drop into the arena.',
    },
    {
        id: 'controls',
        title: 'Your Fighter Ship',
        category: 'CONTROLS',
        text: 'You pilot a <strong>cyan fighter ship</strong> at the bottom of the arena. Use the <strong>← → Arrow Keys</strong> to move left and right. Press <strong>1, 2, or 3</strong> to select a molecule from your deck. Press <strong>SPACE</strong> — or click anywhere in the arena — to launch your shot. The projectile flies from your ship toward the boss.',
        audio: 'You pilot a cyan fighter ship at the bottom of the arena. Use the left and right arrow keys to move. Press 1, 2, or 3 to select a molecule. Press Space — or click the arena — to launch your shot. The projectile flies from your ship toward the boss.',
    },
    {
        id: 'deck',
        title: 'The Molecule Deck',
        category: 'CHEMISTRY',
        text: 'Each round, an AI generates <strong>3 molecule candidates</strong>. The percentage is the <em>composite score</em> — a blend of drugability (QED), ease-of-synthesis (SAS), structural similarity to known drugs, and Lipinski drug-likeness. <strong>Higher score → more damage per hit.</strong> Pick the best one or use ⌨️ Custom to enter your own SMILES.',
        audio: 'Each round, an AI generates 3 molecule candidates. The percentage is the composite score — a blend of drugability, ease of synthesis, structural similarity, and drug-likeness. Higher score means more damage per hit. Pick the best one or enter your own SMILES using the Custom button.',
    },
    {
        id: 'attack',
        title: 'Attack Flow — 3 Phases',
        category: 'COMBAT',
        text: 'When you fire, your shot <strong>locks onto the boss\'s position at that exact moment</strong>. The system then runs 3 scanning phases: <strong>Outer Membrane Scan</strong> → <strong>Binding Site Analysis</strong> → <strong>Quantum Docking</strong>. The first two show fake partial scores to build suspense. The <em>real score</em> — and the actual damage — only appears after phase 3.',
        audio: 'When you fire, your shot locks onto the boss position at that exact moment. The system runs 3 scanning phases: Outer Membrane Scan, then Binding Site Analysis, then Quantum Docking. The first two show fake partial scores. The real score and actual damage only appear after phase 3.',
    },
    {
        id: 'dodge',
        title: 'The Boss Dodges!',
        category: 'COMBAT',
        text: 'The boss <strong>wanders the arena continuously</strong>. When your shot gets close, it may <strong>dodge sideways</strong>! Dodge chance: Easy 20%, Normal 35%, Hard 55% — and it rises by 15% more when the boss is below half health. A miss shows <em>💨 EVADED!</em> and breaks your combo. <strong>Tip:</strong> fire when the boss is cornered or slowing down.',
        audio: 'The boss wanders the arena continuously. When your shot gets close, it may dodge sideways! Dodge chance is 20% on Easy, 35% on Normal, and 55% on Hard — rising further when the boss is below half health. A miss shows EVADED and breaks your combo. Fire when the boss is cornered or slowing down.',
    },
    {
        id: 'threats',
        title: 'Threats & Friendly Fire',
        category: 'SURVIVAL',
        text: '<span style="color:#ff6666"><strong>Red spores</strong></span> fly toward your ship — shoot them to protect your <strong>Quantum Shield (1000 HP)</strong>. But <span style="color:#00ff88"><strong>GREEN cells</strong></span> are healthy host cells — <em>do NOT shoot them!</em> Hitting a green cell triggers <strong>FRIENDLY FIRE: −80 HP</strong> and resets your combo to zero. Use the 🔊 mute button to silence audio if needed.',
        audio: 'Red spores fly toward your ship. Shoot them to protect your Quantum Shield. But green cells are healthy host cells. Do not shoot them! Hitting a green cell triggers Friendly Fire, costs 80 shield points, and resets your combo to zero.',
    },
    {
        id: 'endgame',
        title: 'How to Win',
        category: 'END GAME',
        text: 'The boss has <strong>300 HP</strong>. Each hit deals <strong>5–28 HP</strong> based on composite score. Beating your <em>previous best score</em> gives a <strong>discovery bonus</strong> on top. You need <strong>at least 8 attacks</strong> before the boss can be defeated. When the HP bar hits zero — <strong>you win!</strong> The victory screen shows your best molecule. Hit <strong>🔬 Cross-Validate in ChEMBL</strong> to check if your molecule is a truly novel drug candidate.',
        audio: 'The boss has 300 hit points. Each hit deals 5 to 28 points based on composite score. Beating your previous best gives a discovery bonus on top. You need at least 8 attacks before the boss can die. When the HP bar hits zero, you win! The victory screen shows your best molecule. Cross-validate in ChEMBL to check if it is a truly novel drug candidate. Good luck, Scientist!',
    },
];

// ─── State ──────────────────────────────────────────────────────────────────

let currentStep = 0;
let muted = false;
let audioLoading = false;

const audioEl = document.getElementById('tutAudio');

// ─── Init ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    buildDots();
    goToStep(0);

    window.addEventListener('keydown', e => {
        if (e.code === 'ArrowRight') { e.preventDefault(); tutNext(); }
        if (e.code === 'ArrowLeft')  { e.preventDefault(); tutPrev(); }
        if (e.code === 'Space')      { e.preventDefault(); tutTogglePlay(); }
    });
});

// ─── Navigation ──────────────────────────────────────────────────────────────

window.tutNext = function () {
    stopAudio();
    if (currentStep < TUT_STEPS.length - 1) goToStep(currentStep + 1);
    else location.href = '/game/pathohunt-3d';
};

window.tutPrev = function () {
    stopAudio();
    if (currentStep > 0) goToStep(currentStep - 1);
};

window.tutTogglePlay = function () {
    if (audioLoading) return;
    if (audioEl.paused) {
        if (audioEl.src) {
            audioEl.play().catch(() => {});
        } else {
            playStepAudio(currentStep);
        }
    } else {
        audioEl.pause();
        setWaves(false);
        document.getElementById('playBtn').textContent = '▶ Play Audio';
    }
};

window.tutToggleMute = function () {
    muted = !muted;
    audioEl.muted = muted;
    const btn = document.getElementById('muteBtn');
    btn.textContent = muted ? '🔇' : '🔊';
    btn.classList.toggle('muted', muted);
};

// ─── Step rendering ───────────────────────────────────────────────────────────

function goToStep(idx) {
    currentStep = idx;
    const step = TUT_STEPS[idx];
    const total = TUT_STEPS.length;

    document.getElementById('stepCounter').textContent = `Step ${idx + 1} of ${total}`;
    document.getElementById('progressBar').style.width = `${((idx + 1) / total) * 100}%`;
    document.getElementById('stepCategory').textContent = step.category;
    document.getElementById('stepTitle').textContent = step.title;
    document.getElementById('stepText').innerHTML = step.text;
    document.getElementById('tutVisualLabel').textContent = step.category;
    document.getElementById('prevBtn').disabled = idx === 0;
    document.getElementById('nextBtn').textContent = idx === total - 1 ? 'Enter Battle →' : 'Next →';

    updateDots(idx);
    renderVisual(step.id);
    setWaves(false);
    document.getElementById('playBtn').textContent = '▶ Play Audio';

    // Auto-play audio on each step
    playStepAudio(idx);
}

// ─── Audio ────────────────────────────────────────────────────────────────────

function stopAudio() {
    audioEl.pause();
    audioEl.src = '';
    setWaves(false);
    audioLoading = false;
    document.getElementById('playBtn').textContent = '▶ Play Audio';
    document.getElementById('tutLoading').classList.remove('active');
    document.getElementById('hostAvatar').classList.remove('speaking');
}

async function playStepAudio(idx) {
    stopAudio();
    if (muted) return;
    const step = TUT_STEPS[idx];
    audioLoading = true;
    document.getElementById('tutLoading').classList.add('active');
    document.getElementById('playBtn').textContent = '⏳ Loading...';
    try {
        const resp = await fetch('/api/v3/game/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: step.audio })
        });
        if (!resp.ok) throw new Error('TTS failed');
        const blob = await resp.blob();
        audioEl.src = URL.createObjectURL(blob);
        audioEl.muted = muted;
        await audioEl.play();
        audioLoading = false;
        document.getElementById('tutLoading').classList.remove('active');
        document.getElementById('playBtn').textContent = '⏸ Pause';
        setWaves(true);
        document.getElementById('hostAvatar').classList.add('speaking');
        audioEl.onended = () => {
            setWaves(false);
            document.getElementById('playBtn').textContent = '▶ Play Audio';
            document.getElementById('hostAvatar').classList.remove('speaking');
            // Auto-advance after 2s pause
            if (idx === currentStep && idx < TUT_STEPS.length - 1) {
                setTimeout(() => { if (idx === currentStep) tutNext(); }, 2200);
            }
        };
    } catch (e) {
        audioLoading = false;
        document.getElementById('tutLoading').classList.remove('active');
        document.getElementById('playBtn').textContent = '▶ Play Audio';
    }
}

function setWaves(on) {
    document.getElementById('tutWaves').classList.toggle('active', on);
}

// ─── Dots ─────────────────────────────────────────────────────────────────────

function buildDots() {
    const wrap = document.getElementById('tutDots');
    TUT_STEPS.forEach((_, i) => {
        const d = document.createElement('div');
        d.className = 'tut-dot';
        d.onclick = () => { stopAudio(); goToStep(i); };
        wrap.appendChild(d);
    });
}

function updateDots(active) {
    document.querySelectorAll('.tut-dot').forEach((d, i) => {
        d.className = 'tut-dot' + (i === active ? ' active' : i < active ? ' done' : '');
    });
}

// ─── Visual panels ────────────────────────────────────────────────────────────

function renderVisual(id) {
    const el = document.getElementById('tutVisual');
    const label = el.querySelector('#tutVisualLabel');
    el.innerHTML = '';
    if (label) el.appendChild(label);

    switch (id) {
        case 'overview':     el.innerHTML += buildOverview(); break;
        case 'briefing':     el.innerHTML += buildBriefing(); break;
        case 'controls':     el.innerHTML += buildControls(); break;
        case 'deck':         el.innerHTML += buildDeck(); break;
        case 'attack':       el.innerHTML += buildAttackPhases(); break;
        case 'dodge':        el.innerHTML += buildDodge(); break;
        case 'threats':      el.innerHTML += buildThreats(); break;
        case 'endgame':      el.innerHTML += buildEndgame(); break;
    }
    animateVisual(id);
}

function buildOverview() {
    return `
    <div class="tvis-center">
        <div class="tvis-boss-emoji" style="animation:tvBossPulse 2s ease-in-out infinite">🦠</div>
        <div class="tvis-hp-wrap">
            <div class="tvis-hp-label"><span>BOSS HP</span><span id="tvHpNum">300 / 300</span></div>
            <div class="tvis-hp-track"><div class="tvis-hp-bar" id="tvHpBar" style="width:100%">300 HP</div></div>
        </div>
        <div class="tvis-tag-row">
            <span class="tvis-tag">🦠 Viral Protein</span>
            <span class="tvis-tag" style="color:#f6ad55;border-color:#f6ad55">⚔️ 300 HP</span>
            <span class="tvis-tag" style="color:#3fb950;border-color:#3fb950">🔬 Real Science</span>
        </div>
    </div>`;
}

function buildBriefing() {
    return `
    <div class="tvis-briefing-mock">
        <div class="tvis-brief-emoji">🦠</div>
        <div class="tvis-brief-mission">⚡ MISSION BRIEFING</div>
        <div class="tvis-brief-name">Corona Cutter</div>
        <div class="tvis-brief-lore">The COVID-19 virus uses this molecular scissors to build itself. Your job is to jam those scissors better than Paxlovid.</div>
        <div class="tvis-brief-obj">🎯 Achieve <strong>70%</strong> composite score · deplete 300 HP</div>
        <div class="tvis-brief-ctrl">← → Move · SPACE Fire · 1 / 2 / 3 Select</div>
        <div class="tvis-brief-startbtn">⚔️ START MISSION</div>
    </div>`;
}

function buildControls() {
    return `
    <div class="tvis-ctrl-layout">
        <div class="tvis-ctrl-row">
            <div class="tvis-ctrl-keys">
                <span class="tvis-key tvis-key-arrow">←</span>
                <span class="tvis-key tvis-key-arrow">→</span>
            </div>
            <span class="tvis-ctrl-desc">Move Ship Left / Right</span>
        </div>
        <div class="tvis-ctrl-row">
            <span class="tvis-key tvis-key-wide">SPACE</span>
            <span class="tvis-ctrl-desc">Fire Selected Molecule</span>
        </div>
        <div class="tvis-ctrl-row">
            <div class="tvis-ctrl-keys">
                <span class="tvis-key">1</span>
                <span class="tvis-key">2</span>
                <span class="tvis-key">3</span>
            </div>
            <span class="tvis-ctrl-desc">Select Molecule Card</span>
        </div>
        <div class="tvis-ctrl-row">
            <span class="tvis-ctrl-mouse">🖱️ Click</span>
            <span class="tvis-ctrl-desc">Also fires! (mouse aim)</span>
        </div>
        <div class="tvis-ship-row">
            <div class="tvis-ship" id="tvShip">🚀</div>
            <div class="tvis-ship-label">YOUR SHIP</div>
        </div>
    </div>`;
}

function buildDeck() {
    const cards = [
        { name: 'MX-4203', score: 72, color: '#3fb950', smiles: 'CC(=O)Nc1ccc(O)cc1' },
        { name: 'DL-7819', score: 58, color: '#f6ad55', smiles: 'c1ccc(NC(=O)c2ccco2)cc1' },
        { name: 'CX-3301', score: 41, color: '#ff3e3e', smiles: 'O=C(O)c1ccccc1' },
    ];
    return `
    <div class="tvis-deck">
        ${cards.map((c, i) => `
        <div class="tvis-mol-card ${i === 0 ? 'tvis-selected' : ''}">
            <div class="tvis-mol-key">[${i + 1}]</div>
            <div class="tvis-mol-name">${c.name}</div>
            <div class="tvis-mol-smiles">${c.smiles.substring(0, 18)}...</div>
            <div class="tvis-mol-bar"><div style="width:${c.score}%;background:${c.color}"></div></div>
            <div class="tvis-mol-pct" style="color:${c.color}">${c.score}%</div>
        </div>`).join('')}
    </div>
    <div style="text-align:center;font-size:0.78rem;color:var(--muted);margin-top:8px;">Higher % = more damage per hit</div>`;
}

function buildAttackPhases() {
    return `
    <div class="tvis-phases">
        <div class="tvis-phase tvis-phase-fake">
            <div class="tvis-phase-num">1</div>
            <div class="tvis-phase-name">Outer Membrane</div>
            <div class="tvis-phase-score" style="color:#666">~18% <span class="tvis-fake-tag">PARTIAL</span></div>
        </div>
        <div class="tvis-phase-arrow">→</div>
        <div class="tvis-phase tvis-phase-fake">
            <div class="tvis-phase-num">2</div>
            <div class="tvis-phase-name">Binding Site</div>
            <div class="tvis-phase-score" style="color:#f6ad55">~44% <span class="tvis-fake-tag">PARTIAL</span></div>
        </div>
        <div class="tvis-phase-arrow">→</div>
        <div class="tvis-phase tvis-phase-real">
            <div class="tvis-phase-num">3</div>
            <div class="tvis-phase-name">Quantum Docking</div>
            <div class="tvis-phase-score" style="color:#3fb950">68% <span class="tvis-real-tag">REAL</span></div>
        </div>
    </div>
    <div style="text-align:center;font-size:0.78rem;color:var(--muted);margin-top:12px;">Phases 1 and 2 are fake — real result only after phase 3</div>`;
}

function buildDodge() {
    return `
    <div class="tvis-dodge-arena">
        <div class="tvis-dodge-label" style="color:#888;font-size:0.72rem;text-align:center;margin-bottom:8px;">ARENA VIEW (boss moves continuously)</div>
        <div class="tvis-dodge-stage">
            <div class="tvis-dodge-boss" id="tvDodgeBoss">🦠</div>
            <div class="tvis-dodge-proj" id="tvDodgeProj">💊</div>
            <div class="tvis-dodge-evaded" id="tvDodgeEvaded">💨 EVADED!</div>
        </div>
        <div class="tvis-dodge-chances">
            <span class="tvis-diff-pill diff-easy">Easy: 20%</span>
            <span class="tvis-diff-pill diff-normal">Normal: 35%</span>
            <span class="tvis-diff-pill diff-hard">Hard: 55%</span>
            <span class="tvis-diff-pill diff-wound">Wounded: +15%</span>
        </div>
    </div>`;
}

function buildThreats() {
    return `
    <div class="tvis-threats-row">
        <div class="tvis-threat-card tvis-threat-danger">
            <div class="tvis-threat-emoji">🔴</div>
            <div class="tvis-threat-name">Enemy Spore</div>
            <div class="tvis-threat-action" style="color:#ff3e3e">⚔️ SHOOT IT</div>
            <div class="tvis-threat-desc">Flies toward ship<br>Damages your shield</div>
        </div>
        <div class="tvis-threat-vs">VS</div>
        <div class="tvis-threat-card tvis-threat-safe">
            <div class="tvis-threat-emoji">🟢</div>
            <div class="tvis-threat-name">Healthy Cell</div>
            <div class="tvis-threat-action" style="color:#00ff88">🛡️ AVOID IT</div>
            <div class="tvis-threat-desc">Friendly host cell<br>−80 HP if you shoot it!</div>
        </div>
    </div>
    <div class="tvis-ff-warning">⚠️ Friendly Fire resets your Combo to zero</div>`;
}

function buildEndgame() {
    return `
    <div class="tvis-endgame">
        <div class="tvis-endgame-hp">
            <div class="tvis-hp-label-row"><span>BOSS HP</span><span id="tvEgHpNum">300 / 300</span></div>
            <div class="tvis-hp-track-lg"><div class="tvis-hp-bar-lg" id="tvEgBar" style="width:100%">300 HP</div></div>
        </div>
        <div class="tvis-win-conditions">
            <div class="tvis-win-row">
                <span class="tvis-win-icon">⚔️</span>
                <span>Fire at least <strong>8 attacks</strong> (required minimum)</span>
            </div>
            <div class="tvis-win-row">
                <span class="tvis-win-icon">💥</span>
                <span>Each hit deals <strong>5–28 HP</strong> based on composite score</span>
            </div>
            <div class="tvis-win-row">
                <span class="tvis-win-icon">🏆</span>
                <span>Beat your best score = <strong>Discovery Bonus</strong> damage</span>
            </div>
            <div class="tvis-win-row tvis-win-goal">
                <span class="tvis-win-icon">🎯</span>
                <span>Boss HP reaches <strong>0 → VICTORY!</strong></span>
            </div>
            <div class="tvis-win-row tvis-win-bonus">
                <span class="tvis-win-icon">🔬</span>
                <span>Cross-validate in ChEMBL to confirm novelty</span>
            </div>
        </div>
    </div>`;
}

// ─── Animations after render ──────────────────────────────────────────────────

function animateVisual(id) {
    if (id === 'overview') {
        // HP bar drains and refills in a loop
        const bar = document.getElementById('tvHpBar');
        const num = document.getElementById('tvHpNum');
        if (!bar) return;
        let hp = 300, dir = -1;
        const iv = setInterval(() => {
            hp += dir * 3;
            if (hp <= 60) dir = 1;
            if (hp >= 300) dir = -1;
            bar.style.width = (hp / 300 * 100) + '%';
            bar.textContent = Math.round(hp) + ' HP';
            if (num) num.textContent = Math.round(hp) + ' / 300';
        }, 80);
        bar._iv = iv;
    }

    if (id === 'controls') {
        // Ship bounces left and right
        const ship = document.getElementById('tvShip');
        if (!ship) return;
        let x = 0, dir = 1;
        const iv = setInterval(() => {
            x += dir * 1.5;
            if (x > 50) dir = -1;
            if (x < -50) dir = 1;
            ship.style.transform = `translateX(${x}px) rotate(${dir > 0 ? 5 : -5}deg)`;
        }, 30);
        ship._iv = iv;
    }

    if (id === 'dodge') {
        // Boss darts sideways, projectile flies past, EVADED! flashes
        const boss = document.getElementById('tvDodgeBoss');
        const proj = document.getElementById('tvDodgeProj');
        const evaded = document.getElementById('tvDodgeEvaded');
        if (!boss || !proj || !evaded) return;
        let phase = 0;
        const seq = () => {
            if (phase === 0) {
                // reset
                boss.style.transition = 'left 0.3s'; boss.style.left = '50%';
                proj.style.transition = 'none'; proj.style.bottom = '-20px'; proj.style.opacity = '0';
                evaded.style.opacity = '0';
                setTimeout(() => { phase = 1; seq(); }, 1000);
            } else if (phase === 1) {
                // projectile fires upward
                proj.style.opacity = '1';
                proj.style.transition = 'bottom 1.2s linear'; proj.style.bottom = '55%';
                setTimeout(() => { phase = 2; seq(); }, 800);
            } else if (phase === 2) {
                // boss dodges
                boss.style.transition = 'left 0.4s'; boss.style.left = '75%';
                setTimeout(() => { phase = 3; seq(); }, 400);
            } else if (phase === 3) {
                // proj flies past
                proj.style.transition = 'bottom 0.4s linear'; proj.style.bottom = '100%';
                setTimeout(() => { phase = 4; seq(); }, 400);
            } else if (phase === 4) {
                // EVADED
                evaded.style.transition = 'opacity 0.2s'; evaded.style.opacity = '1';
                setTimeout(() => { phase = 0; seq(); }, 1500);
            }
        };
        seq();
    }

    if (id === 'endgame') {
        // HP bar drains slowly to 0 then victory flash
        const bar = document.getElementById('tvEgBar');
        const num = document.getElementById('tvEgHpNum');
        if (!bar) return;
        let hp = 300;
        const drain = setInterval(() => {
            hp -= 4;
            if (hp <= 0) {
                hp = 0;
                bar.style.width = '0%';
                bar.textContent = '0 HP';
                if (num) num.textContent = '0 / 300';
                clearInterval(drain);
                // Flash victory
                setTimeout(() => {
                    bar.style.width = '100%';
                    bar.textContent = '🏆 VICTORY!';
                    bar.style.background = 'linear-gradient(90deg,#3fb950,#4ade80)';
                    if (num) num.textContent = 'WON!';
                }, 1200);
                return;
            }
            bar.style.width = (hp / 300 * 100) + '%';
            bar.textContent = Math.round(hp) + ' HP';
            if (num) num.textContent = Math.round(hp) + ' / 300';
        }, 60);
    }
}
