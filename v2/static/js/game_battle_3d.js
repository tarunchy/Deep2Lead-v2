// Global audio manager — pre-cached TTS, pause/resume, mute
const audioMgr = {
    current: null,
    cache: {},      // key -> Blob (pre-generated)
    paused: false,  // soft pause — audio can resume
    muted: true,    // hard mute — off by default; user enables via story screen toggle

    // Play a raw blob immediately
    play(blob) {
        this.stop();
        if (this.muted || this.paused) return;
        const audio = new Audio(URL.createObjectURL(blob));
        this.current = audio;
        audio.play().catch(() => {});
        audio.onended = () => { this.current = null; };
    },

    // Play from pre-generated cache
    playKey(key) {
        const blob = this.cache[key];
        if (blob) this.play(blob);
    },

    // Pre-generate a batch of clips in parallel: { key: 'text', ... }
    async preload(clips) {
        const entries = Object.entries(clips).filter(([, t]) => t && t.length > 0);
        await Promise.allSettled(entries.map(async ([key, text]) => {
            try {
                const r = await fetch('/api/v3/game/tts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: String(text).substring(0, 300) })
                });
                if (r.ok) this.cache[key] = await r.blob();
            } catch (_) {}
        }));
    },

    stop() {
        if (this.current) { this.current.pause(); URL.revokeObjectURL(this.current.src); this.current = null; }
    },

    // Soft pause — click button to resume
    pause() {
        this.paused = true;
        if (this.current && !this.current.paused) this.current.pause();
        this._updateBtn();
    },

    // Resume from soft pause
    resume() {
        this.paused = false;
        if (this.current && this.current.paused && !this.muted) this.current.play().catch(() => {});
        this._updateBtn();
    },

    togglePause() { this.paused ? this.resume() : this.pause(); },

    // Hard mute (M key)
    toggleMute() {
        this.muted = !this.muted;
        if (this.muted) this.stop();
        this._updateBtn();
    },

    // Backward-compat (button click → pause toggle)
    toggle() { this.togglePause(); },

    _updateBtn() {
        const btn = document.getElementById('btnMute');
        if (!btn) return;
        if (this.muted)        { btn.textContent = '🔇'; btn.title = 'Unmute (M)'; }
        else if (this.paused)  { btn.textContent = '⏸️'; btn.title = 'Resume audio'; }
        else                   { btn.textContent = '🔊'; btn.title = 'Pause audio (M = mute)'; }
    }
};

const BOSS_PROFILES = {
    influenza_na: {
        color: 0x4488ff, emissive: 0x001133, secondaryColor: 0x88aaff,
        buildMesh: () => {
            const geo = new THREE.IcosahedronGeometry(5, 1);
            return new THREE.Mesh(geo, new THREE.MeshPhongMaterial({ color: 0x4488ff, emissive: 0x001133, flatShading: true }));
        },
        rotY: 0.012, rotX: 0.006, idleAnim: 'pulse', sporeColor: 0x4488ff,
    },
    covid19_mpro: {
        color: 0xff6600, emissive: 0x330a00,
        buildMesh: () => {
            const g = new THREE.Group();
            g.add(new THREE.Mesh(new THREE.TorusKnotGeometry(4, 1.2, 120, 16), new THREE.MeshPhongMaterial({ color: 0xff6600, emissive: 0x330a00, flatShading: true })));
            for (let i = 0; i < 8; i++) {
                const spike = new THREE.Mesh(new THREE.ConeGeometry(0.4, 2, 6), new THREE.MeshPhongMaterial({ color: 0xffaa44, emissive: 0x220000 }));
                const a = (i / 8) * Math.PI * 2;
                spike.position.set(Math.cos(a) * 6.5, Math.sin(a) * 6.5, 0);
                spike.lookAt(0, 0, 0); spike.rotateX(Math.PI / 2);
                g.add(spike);
            }
            return g;
        },
        rotY: 0.018, rotX: 0.004, idleAnim: 'spin', sporeColor: 0xff6600,
    },
    hiv_protease: {
        color: 0xff2222, emissive: 0x330000,
        buildMesh: () => {
            const g = new THREE.Group();
            [[0,0,0],[5,3,0],[-5,3,0],[5,-3,0],[-5,-3,0]].forEach(([x,y,z], i) => {
                const m = new THREE.Mesh(new THREE.OctahedronGeometry(i===0?3.5:2, 0),
                    new THREE.MeshPhongMaterial({ color: i===0?0xff2222:0xff4444, emissive: 0x330000, wireframe: i>0 }));
                m.position.set(x,y,z); g.add(m);
            });
            return g;
        },
        rotY: 0.01, rotX: 0.008, idleAnim: 'orbit', sporeColor: 0xff2222,
    },
    egfr_kinase: {
        color: 0xaa44ff, emissive: 0x110033,
        buildMesh: () => {
            const g = new THREE.Group();
            g.add(new THREE.Mesh(new THREE.TorusGeometry(4, 1.2, 16, 32), new THREE.MeshPhongMaterial({ color: 0xaa44ff, emissive: 0x110033 })));
            const r2 = new THREE.Mesh(new THREE.TorusGeometry(5.5, 0.25, 8, 32), new THREE.MeshPhongMaterial({ color: 0xdd88ff, wireframe: true }));
            r2.rotation.x = Math.PI / 3; g.add(r2);
            const r3 = new THREE.Mesh(new THREE.TorusGeometry(6.8, 0.15, 8, 32), new THREE.MeshPhongMaterial({ color: 0xcc66ff, wireframe: true }));
            r3.rotation.x = -Math.PI / 4; r3.rotation.y = Math.PI / 6; g.add(r3);
            return g;
        },
        rotY: 0.016, rotX: 0.004, idleAnim: 'spin', sporeColor: 0xaa44ff,
    },
    braf_v600e: {
        color: 0xffcc00, emissive: 0x221100,
        buildMesh: () => {
            const geo = new THREE.BoxGeometry(7,7,7,3,3,3);
            const pos = geo.attributes.position;
            for (let i = 0; i < pos.count; i++) pos.setXYZ(i, pos.getX(i)+(Math.random()-.5)*2.5, pos.getY(i)+(Math.random()-.5)*2.5, pos.getZ(i)+(Math.random()-.5)*2.5);
            geo.computeVertexNormals();
            return new THREE.Mesh(geo, new THREE.MeshPhongMaterial({ color: 0xffcc00, emissive: 0x221100, flatShading: true }));
        },
        rotY: 0.009, rotX: 0.018, idleAnim: 'twitch', sporeColor: 0xffcc00,
    },
    sirt1: {
        color: 0xcccccc, emissive: 0x222222,
        buildMesh: () => new THREE.Mesh(new THREE.TorusKnotGeometry(4.5, 0.8, 200, 20, 2, 3), new THREE.MeshPhongMaterial({ color: 0xcccccc, emissive: 0x222222, transparent: true, opacity: 0.85 })),
        rotY: 0.006, rotX: 0.002, idleAnim: 'float', sporeColor: 0xaaaaaa,
    },
    cdk2: {
        color: 0xff4400, emissive: 0x220000,
        buildMesh: () => {
            const g = new THREE.Group();
            g.add(new THREE.Mesh(new THREE.CylinderGeometry(3,3,8,8), new THREE.MeshPhongMaterial({ color: 0xff4400, emissive: 0x220000, flatShading: true })));
            g.userData.orbs = [];
            for (let i = 0; i < 4; i++) {
                const orb = new THREE.Mesh(new THREE.SphereGeometry(1.2, 8, 8), new THREE.MeshPhongMaterial({ color: 0xff6600, emissive: 0x110000 }));
                const angle = (i / 4) * Math.PI * 2;
                orb.position.set(Math.cos(angle)*7, 0, Math.sin(angle)*7);
                g.add(orb);
                g.userData.orbs.push({ mesh: orb, angle, speed: 0.025 });
            }
            return g;
        },
        rotY: 0.02, rotX: 0, idleAnim: 'timer', sporeColor: 0xff4400,
    },
};
BOSS_PROFILES.default = BOSS_PROFILES.covid19_mpro;

const THEMES = {
    jungle: { bg: 0x000a1a, fog: 0x000a1a, floor: 0x002233, env: 0x00ff88, name: "BIO_JUNGLE_7" },
    space:  { bg: 0x000000, fog: 0x050010, floor: 0x110022, env: 0xffffff, name: "ORBITAL_VOID" },
    sky:    { bg: 0x87ceeb, fog: 0xb0e2ff, floor: 0xffffff, env: 0xffffff, name: "STRATOSPHERE" },
    ocean:  { bg: 0x001a2e, fog: 0x002b4d, floor: 0x004d80, env: 0x00f2ff, name: "ABYSS_TRENCH" },
    desert: { bg: 0x2e1a00, fog: 0x4d2b00, floor: 0x804d00, env: 0xffcc00, name: "SILICA_DUNE" },
    city:   { bg: 0x050505, fog: 0x111111, floor: 0x222222, env: 0xff00ff, name: "NEON_METRO" },
};

const DIFFICULTY = {
    easy:   { speedMin: 0.015, speedMax: 0.04,  smallDmg: 5,   largeDmg: 10,  largeHealth: 1, spawnRate: 6000 },
    normal: { speedMin: 0.06,  speedMax: 0.15,  smallDmg: 10,  largeDmg: 20,  largeHealth: 2, spawnRate: 4000 },
    hard:   { speedMin: 0.25,  speedMax: 0.5,   smallDmg: 25,  largeDmg: 50,  largeHealth: 3, spawnRate: 2500 },
};

function molCodename(smiles) {
    let h = 0;
    for (let c of smiles) h = (h * 31 + c.charCodeAt(0)) & 0xffffffff;
    const p = ["CX","DL","VK","MX","BT","ZR","PH","QL"][(h >>> 0) % 8];
    return `${p}-${((h >>> 0) % 9000) + 1000}`;
}

function toStars(val, max) {
    const stars = Math.round((val / (max || 1)) * 5);
    return '★'.repeat(Math.max(0, stars)) + '☆'.repeat(Math.max(0, 5 - stars));
}

function sasToStars(sas) {
    return toStars(1 - (sas - 1) / 9, 1);
}

const DOCKING_FACTS = [
    { title: "How Molecular Docking Works", body: "Your molecule is being computationally fitted into the pathogen's active site — like a key into a lock. The docking score predicts how tightly it binds.", term: "Binding Affinity", def: "How strongly a drug sticks to its target protein. Measured in Ki or IC50 — lower values mean tighter binding and stronger inhibition of the pathogen." },
    { title: "Lipinski's Rule of 5", body: "Good oral drugs follow 5 rules: MW < 500 Da, LogP < 5, H-bond donors ≤ 5, acceptors ≤ 10. Violating these often predicts poor absorption through the gut wall.", term: "Bioavailability", def: "The fraction of a drug that reaches the bloodstream after oral dosing. Poor bioavailability = drug never reaches its target, no matter how potent it is." },
    { title: "QED — Drug-likeness Score", body: "QED (Quantitative Estimate of Drug-likeness) scores molecules 0–1. Aspirin ≈ 0.55, Ibuprofen ≈ 0.73. Above 0.6 is considered strongly drug-like.", term: "Drug-likeness", def: "A composite score of molecular properties predicting oral drug potential. The higher the QED, the more likely the molecule behaves like a real medicine." },
    { title: "Synthesis Accessibility", body: "A brilliant molecule is useless if chemists can't make it. SAS scores synthesis difficulty 1 (trivial) to 10 (near impossible). Simple ring systems score lower — aim for ≤ 4.", term: "SAS Score", def: "Synthesis Accessibility Score (1–10). Most approved drugs score 2–4. Complex or rare bond patterns push the score up and make manufacturing harder." },
    { title: "ADMET — Beyond Binding", body: "Even a perfect binder can fail if it's toxic, unstable in the body, or excreted too fast. Over 90% of drug candidates fail in clinical trials — mostly due to ADMET failures, not potency.", term: "ADMET", def: "Absorption, Distribution, Metabolism, Excretion, Toxicity. Five key properties that determine whether a drug actually works safely in a living patient." },
    { title: "Structure–Activity Relationship", body: "Tiny changes to a molecule can completely change its potency. Adding one fluorine atom, flipping a ring, or changing a linker can make or break a drug candidate.", term: "SAR", def: "Structure–Activity Relationship: the study of how molecular structure changes affect biological activity. The core tool used by medicinal chemists every day." },
    { title: "The Active Site Pocket", body: "The pathogen's protein has a precise 3D pocket lined with amino acids. Your molecule must complement its shape and charge to lock in and block the enzyme.", term: "Active Site", def: "The specific region of a protein where a drug binds. Blocking it can halt the pathogen's critical function — this is the goal of all enzyme inhibitor drugs." },
    { title: "Real Drug Discovery", body: "Tamiflu (Oseltamivir) took 10+ years and ~$1 billion to develop before it could block Influenza NA. In this game you're compressing that entire journey into seconds!", term: "Drug Discovery Timeline", def: "On average, 12–15 years and $2.6 billion separate an idea from an approved drug. Only 1 in ~10,000 screened compounds ever reaches a patient." },
];

function getAttackMsg(composite, bossName, isNewBest) {
    const nb = isNewBest ? ' 🏆 New best!' : '';
    if (composite >= 0.80) return `Perfect strike! Your molecule nearly perfectly blocks ${bossName}.${nb}`;
    if (composite >= 0.70) return `Excellent hit! Better than known drugs against ${bossName}.${nb}`;
    if (composite >= 0.60) return `Good hit! The molecule shows real therapeutic potential.${nb}`;
    if (composite >= 0.50) return `Moderate hit. Keep improving molecular properties.${nb}`;
    if (composite >= 0.40) return `Weak hit. Try a different molecular structure.`;
    return `Minimal effect. The pathogen barely noticed. Keep experimenting!`;
}

class PathoHunt3D {
    constructor() {
        this.container = document.getElementById('gameViewport');
        this.canvas = document.getElementById('render-canvas');
        this.scene = null; this.camera = null; this.renderer = null;
        this.monster = null; this.envGroup = null;
        this.projectiles = []; this.explosions = []; this.obstacles = [];
        this.bossHP = window.GAME_INITIAL_HP || 300;
        this.bossInitialHP = window.GAME_INITIAL_HP || 300;
        this.playerHP = 1000;
        this.sessionId = null;
        this.isGameOver = false;
        this.attackLocked = false;
        this.deckSize = 1; // single molecule at a time (configurable 1-3 before mission starts)
        this.currentDeck = [];
        this.selectedCardIdx = 0;
        this.selectedSmiles = window.GAME_STARTER_SMILES || '';
        this.selectedMolName = 'SEED';
        this.bestScore = 0;
        this.knownScore = window.GAME_KNOWN_SCORE || 0.60;
        this.winThreshold = this.knownScore + 0.05; // discovery: beat known drug by 5%
        this.attackCount = 0;
        this.journeyDots = [];       // [{composite, molName}]
        this.consecutiveLowScores = 0;  // hint system trigger
        this.scienceCardTimer = null;
        this.mouse = new THREE.Vector2();
        this.raycaster = new THREE.Raycaster();
        this.isAiming = false;
        this.targetPoint = new THREE.Vector3();
        this.spawnTimer = null;
        this.wonMolecule = null;
        this.bossProfile = BOSS_PROFILES[window.GAME_BOSS_ID] || BOSS_PROFILES.default;

        // Real-game state
        this.keys = {};
        this.playerShipX = 0;
        this.playerShipY = -7;   // vertical position (up/down)
        this.playerShip = null;
        this.bossTargetX = 0;
        this.bossTargetY = 5;
        this.bossMoveTimer = 0;
        this.safeObjects = [];
        this.safeSpawnTimer = null;
        this.comboCount = 0;
        this.gameStarted = false;
        this.lastFrameTime = Date.now();
        this.fireReady = true;
        this.fireCooldown = 800;
        this._warned300 = false;
        this._warned150 = false;

        // Dodge system
        this.bossEvasionMode = false;
        this.bossEvadeTimer = 0;
        this.dodgeCooldown = false;

        // Phase / mutation / outbreak / pinning / notebook
        this.bossPhase = 0;
        this.pinnedSmiles = null;
        this.outbreakMode = false;
        this.outbreakTimeLeft = 480;
        this.outbreakTimer = null;
        this.attackLog = [];       // [{n, composite, molName}]
        this.totalRp = 0;

        this.init();
    }

    async init() {
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(75, this.container.clientWidth / this.container.clientHeight, 0.1, 1000);
        this.camera.position.set(0, 5, 45);
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.canvas.appendChild(this.renderer.domElement);
        this.envGroup = new THREE.Group();
        this.scene.add(this.envGroup);
        this.scene.add(new THREE.AmbientLight(0xffffff, 0.4));
        const light = new THREE.PointLight(0x00f2ff, 1.5, 100);
        light.position.set(20, 20, 20);
        this.scene.add(light);
        this.monster = this.bossProfile.buildMesh();
        this.monster.position.set(0, 5, 0);
        this.scene.add(this.monster);
        this.applyTheme('jungle');
        this.buildPlayerShip();
        this.setupEventListeners();
        this.animate();
        await this.startSession();
        // preloadAudio() is deferred until user opts in via voice toggle in story screen
        this.showStoryScreen();
    }

    preloadAudio() {
        const boss = window.GAME_BOSS_NAME || 'the pathogen';
        const ps   = window.GAME_PATIENT_STORY || {};

        const clips = {
            // Evade taunts
            evade_0: 'Ooh, you missed! The pathogen dodged your molecule. Try again!',
            evade_1: 'So close! It slipped away. Pick a better molecule and fire!',
            evade_2: "Ha! The target evaded. Don't give up — hit it harder next time!",
            evade_3: 'Missed! The pathogen is fast. Adjust your aim and try again!',

            // Friendly fire
            ff_0: 'Oh no, you destroyed a healthy cell! The patient loses 80 hit points!',
            ff_1: 'That was a friendly cell! Watch your targeting — minus 80 hit points!',
            ff_2: 'Oof, friendly fire! You just nuked a healthy cell. Minus 80 hit points!',
            ff_3: 'Careful! You hit a friendly cell. The patient is taking damage — minus 80 hit points!',

            // HP warnings
            warn_300: 'Warning! Host defences are critical. Destroy the pathogen now or the mission fails!',
            warn_150: 'Critical alert! Immune system collapse imminent. Fire your best molecule immediately!',

            // Attack quality messages (uses boss name so generate after boss is known)
            hit_perfect:   `Perfect strike! Your molecule nearly perfectly blocks ${boss}.`,
            hit_excellent: `Excellent hit! Better than known drugs against ${boss}.`,
            hit_good:      'Good hit! The molecule shows real therapeutic potential.',
            hit_moderate:  'Moderate hit. Keep improving molecular properties.',
            hit_weak:      'Weak hit. Try a different molecular structure.',
            hit_minimal:   'Minimal effect. The pathogen barely noticed. Keep experimenting!',

            // Phase taunts
            phase2: window.GAME_PHASE2_TAUNT || '',
            phase3: window.GAME_PHASE3_TAUNT || '',

            // Patient intro narration
            patient_intro: ps.name ? `Patient ${ps.name}, age ${ps.age}. ${ps.urgency || ''}` : '',

            // Outbreak escalation
            outbreak_escalate: 'Warning! Outbreak is escalating — pathogen spore pressure rising!',

            // Boss intro fallback (no patient story)
            boss_intro: (window.GAME_PLAIN_ENGLISH || window.GAME_BOSS_FLAVOR || '').substring(0, 280),

            // Patient outcomes — known from game_levels.json at page load
            patient_win:  (ps.outcome_win  || '').substring(0, 280),
            patient_loss: (ps.outcome_loss || '').substring(0, 280),
        };

        // Pre-generate all mutation descriptions
        (window.GAME_MUTATION_POOL || []).forEach(m => {
            if (m.id && m.name) {
                clips[`mut_${m.id}`] = `Pathogen mutation detected: ${m.name}. ${(m.description || '').substring(0, 150)}`;
            }
        });

        // Show a subtle loading indicator on the mute button while pre-generating
        const btn = document.getElementById('btnMute');
        if (btn) { btn.textContent = '⏳'; btn.title = 'Pre-loading audio…'; }
        audioMgr.preload(clips).then(() => {
            audioMgr._updateBtn();
        });
    }

    buildPlayerShip() {
        const g = new THREE.Group();
        const bodyMat = new THREE.MeshPhongMaterial({ color: 0x00f2ff, emissive: 0x003344 });
        const body = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 1.2, 4, 6), bodyMat);
        body.rotation.x = Math.PI / 2;
        g.add(body);

        const wingMat = new THREE.MeshPhongMaterial({ color: 0x0088aa, emissive: 0x001122 });
        const wingGeoL = new THREE.ConeGeometry(0.5, 3.5, 4);
        const wL = new THREE.Mesh(wingGeoL, wingMat);
        wL.rotation.z = Math.PI / 2;
        wL.position.set(-2.8, 0, 0.5);
        g.add(wL);

        const wR = new THREE.Mesh(wingGeoL, wingMat);
        wR.rotation.z = -Math.PI / 2;
        wR.position.set(2.8, 0, 0.5);
        g.add(wR);

        const thrusterMat = new THREE.MeshPhongMaterial({ color: 0xff6600, emissive: 0xff3300 });
        const thruster = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.2, 1, 6), thrusterMat);
        thruster.rotation.x = Math.PI / 2;
        thruster.position.set(0, 0, 2.5);
        g.add(thruster);
        g.userData.thruster = thruster;

        g.position.set(0, -8, 32);
        this.scene.add(g);
        this.playerShip = g;
    }

    showStoryScreen() {
        const overlay = document.getElementById('storyScreen');
        if (!overlay) { this.startBattle(); return; }

        // ── Slide 0: Patient story ───────────────────────────────
        const ps = window.GAME_PATIENT_STORY || {};
        const nameEl = document.getElementById('patientName');
        if (nameEl) nameEl.textContent = ps.name ? `${ps.name}, age ${ps.age}` : (window.GAME_BOSS_NAME || 'Unknown Patient');
        const statsEl = document.getElementById('patientStats');
        if (statsEl) statsEl.textContent = ps.condition || '';
        const urgEl = document.getElementById('patientUrgency');
        if (urgEl) urgEl.textContent = ps.urgency ? `🚨 ${ps.urgency}` : '';

        // ── Slide 1: Boss science ────────────────────────────────
        const bossNameEl = document.getElementById('storyBossName');
        const emojiEl = document.getElementById('storyBossEmoji');
        const textEl = document.getElementById('storyText');
        const winEl = document.getElementById('storyWinPct');
        const knownEl = document.getElementById('storyKnownPct');
        if (bossNameEl) bossNameEl.textContent = window.GAME_BOSS_NAME || window.GAME_BOSS_ID;
        if (emojiEl) emojiEl.textContent = window.GAME_BOSS_EMOJI || '🦠';
        if (textEl) textEl.textContent = window.GAME_PLAIN_ENGLISH || window.GAME_BOSS_FLAVOR || 'A dangerous pathogen is threatening the host.';
        if (winEl) winEl.textContent = Math.round((this.winThreshold || 0.70) * 100) + '%';
        if (knownEl) knownEl.textContent = Math.round(this.knownScore * 100) + '%';

        // ── Carousel logic ───────────────────────────────────────
        let currentSlide = ps.name ? 0 : 1;
        const totalSlides = ps.name ? 3 : 2;
        const slideIds = ps.name ? ['slide-0', 'slide-1', 'slide-2'] : ['slide-1', 'slide-2'];

        const showSlide = (idx) => {
            currentSlide = idx;
            slideIds.forEach((sid, i) => {
                const el = document.getElementById(sid);
                if (el) el.classList.toggle('active-slide', i === idx);
            });
            const dots = overlay.querySelectorAll('.story-dot');
            dots.forEach((d, i) => d.classList.toggle('active', i === idx));
            const prev = document.getElementById('storyPrev');
            const next = document.getElementById('storyNext');
            if (prev) prev.disabled = idx === 0;
            if (next) {
                if (idx >= slideIds.length - 1) {
                    next.style.display = 'none';
                } else {
                    next.style.display = '';
                    next.textContent = idx === 0 ? 'Science ▶' : 'Controls ▶';
                }
            }
        };

        showSlide(currentSlide);
        overlay.style.display = 'flex';

        document.getElementById('storyPrev')?.addEventListener('click', () => showSlide(Math.max(0, currentSlide - 1)));
        document.getElementById('storyNext')?.addEventListener('click', () => showSlide(Math.min(slideIds.length - 1, currentSlide + 1)));
        overlay.querySelectorAll('.story-dot').forEach((d, i) => d.addEventListener('click', () => showSlide(i)));

        // Voice toggle: enable/disable preloading in real time
        document.getElementById('voiceToggle')?.addEventListener('change', e => {
            if (e.target.checked) {
                audioMgr.muted = false;
                audioMgr._updateBtn();
                if (!this._audioPreloaded) {
                    this._audioPreloaded = true;
                    this.preloadAudio();
                }
            } else {
                audioMgr.muted = true;
                audioMgr.stop();
                audioMgr._updateBtn();
            }
        });

        const startBtn = document.getElementById('storyStartBtn');
        if (startBtn) {
            startBtn.addEventListener('click', () => {
                this.outbreakMode = document.getElementById('outbreakToggle')?.checked || false;
                overlay.style.display = 'none';
                this.startBattle();
            });
        }

        // Narrate patient intro or boss intro — both pre-generated
        if (ps.name) audioMgr.playKey('patient_intro');
        else audioMgr.playKey('boss_intro');
    }

    startBattle() {
        this.gameStarted = true;
        this.updateSpawnRate();
        this.startSafeSpawner();
        this.renderDeckLoading();
        this.fetchDeck();
        this.updateWinMarker();
        this.log(`MISSION STARTED — TARGET: ${window.GAME_BOSS_NAME || window.GAME_BOSS_ID}`);
        this.loadLeaderboard();
        if (this.outbreakMode) this.startOutbreakTimer();
    }

    startSafeSpawner() {
        if (this.safeSpawnTimer) clearInterval(this.safeSpawnTimer);
        this.safeSpawnTimer = setInterval(() => this.spawnSafeObject(), 3500);
        setTimeout(() => this.spawnSafeObject(), 800);
    }

    spawnSafeObject() {
        if (this.isGameOver || !this.gameStarted) return;
        const size = 0.8 + Math.random() * 1.2;
        const mesh = new THREE.Mesh(
            new THREE.OctahedronGeometry(size, 1),
            new THREE.MeshPhongMaterial({ color: 0x00ff88, emissive: 0x004422, transparent: true, opacity: 0.85 })
        );
        mesh.position.set((Math.random() - 0.5) * 70, Math.random() * 22 - 4, -60);
        const speed = 0.05 + Math.random() * 0.07;
        mesh.userData.velocity = new THREE.Vector3((Math.random() - 0.5) * 0.04, Math.sin(Date.now() * 0.001 + Math.random() * 6) * 0.008, speed);
        mesh.userData.pulseT = Math.random() * Math.PI * 2;
        mesh.userData.isSafe = true;
        this.scene.add(mesh);
        this.safeObjects.push(mesh);
    }

    triggerDodge() {
        if (!this.gameStarted || !this.monster) return;
        this.dodgeCooldown = true;
        this.bossEvasionMode = true;
        // Snap to an evasion target far from current position
        const side = Math.random() > 0.5 ? 1 : -1;
        this.bossTargetX = side * (12 + Math.random() * 16);
        this.bossTargetY = 3 + Math.random() * 10;
        this.bossMoveTimer = Date.now() + 1500; // hold evasion target for 1.5s
        // Quick rotation flash
        this.monster.traverse(m => {
            if (m.isMesh && m.material) {
                const orig = m.material.emissive?.getHex?.() || 0;
                m.material.emissive?.setHex(0xffaa00);
                setTimeout(() => m.material.emissive?.setHex(orig), 300);
            }
        });
        setTimeout(() => {
            this.bossEvasionMode = false;
            this.dodgeCooldown = false;
        }, 2200);
    }

    onProjectileMiss(proj, idx) {
        this.scene.remove(proj.mesh);
        if (idx !== undefined) this.projectiles.splice(idx, 1);
        else {
            const i = this.projectiles.indexOf(proj);
            if (i > -1) this.projectiles.splice(i, 1);
        }
        this.attackLocked = false;
        this.comboCount = 0;
        this.consecutiveLowScores = (this.consecutiveLowScores || 0) + 1;
        this.updateComboDisplay();
        this.log('Molecule missed the binding pocket — every test is data!', '#f6ad55');

        // Floating miss feedback
        const div = document.createElement('div');
        div.className = 'float-dmg';
        div.style.cssText = 'color:#f6ad55;font-size:18px;font-weight:900;';
        div.textContent = '🔬 No pocket fit — adjust scaffold!';
        const rect = this.container.getBoundingClientRect();
        div.style.left = (rect.width * 0.42 + (Math.random() - 0.5) * 50) + 'px';
        div.style.top = (rect.height * 0.32) + 'px';
        this.container.appendChild(div);
        setTimeout(() => div.remove(), 1800);

        // Flash orange instead of red
        const vd = document.getElementById('vfx-flash');
        if (vd) {
            vd.style.background = 'rgba(255,120,0,0.18)';
            vd.style.opacity = '1';
            setTimeout(() => { vd.style.opacity = '0'; setTimeout(() => { vd.style.background = ''; }, 200); }, 220);
        }
        // Miss = molecule not consumed — keep deck as-is, just unlock

        // Taunt voice line (pre-generated)
        audioMgr.playKey(`evade_${Math.floor(Math.random() * 4)}`);
    }

    friendlyFire() {
        this.comboCount = 0;
        this.updateComboDisplay();
        this.takeDamage(80);
        this.attackLocked = false;
        this.log('FRIENDLY FIRE! Healthy cell destroyed! -80 HP', '#ff6600');

        const vf = document.getElementById('vfx-flash');
        if (vf) {
            vf.style.background = 'rgba(0,255,136,0.35)';
            vf.style.opacity = '1';
            setTimeout(() => { vf.style.opacity = '0'; setTimeout(() => { vf.style.background = ''; }, 200); }, 250);
        }

        const div = document.createElement('div');
        div.className = 'float-dmg';
        div.style.color = '#ff6600';
        div.style.fontSize = '20px';
        div.textContent = '⚠️ FRIENDLY FIRE -80 HP';
        const rect = this.container.getBoundingClientRect();
        div.style.left = (rect.width * 0.3 + (Math.random() - 0.5) * 40) + 'px';
        div.style.top = (rect.height * 0.42) + 'px';
        this.container.appendChild(div);
        setTimeout(() => div.remove(), 2200);

        // Big centred horror message
        const msgs = [
            'Oh no! You destroyed a healthy cell! 😱',
            'That was a friendly cell! Watch your aim! 💔',
            'Oof! You just nuked a healthy cell! 😬',
            'Friendly fire! The patient is suffering! 🩸',
        ];
        const msgDiv = document.createElement('div');
        msgDiv.className = 'ff-alert';
        msgDiv.textContent = msgs[Math.floor(Math.random() * msgs.length)];
        this.container.appendChild(msgDiv);
        setTimeout(() => msgDiv.remove(), 2800);

        // Friendly-fire voice line (pre-generated)
        audioMgr.playKey(`ff_${Math.floor(Math.random() * 4)}`);

        // Molecule was consumed by friendly cell — replace only that slot
        setTimeout(() => this.refreshOneCard(this.firedCardIdx ?? 0), 300);
    }

    updateComboDisplay() {
        const badge = document.getElementById('comboBadge');
        if (!badge) return;
        if (this.comboCount >= 2) {
            badge.textContent = this.comboCount >= 5 ? `🔥🔥 ${this.comboCount}x Optimization Streak` : `🔥 ${this.comboCount}x Optimization Streak`;
            badge.style.display = 'block';
            badge.className = 'combo-badge optimization-streak' + (this.comboCount >= 5 ? ' combo-hot' : '');
        } else {
            badge.style.display = 'none';
        }
    }

    async startSession() {
        try {
            const resp = await fetch('/api/v3/game/session/start', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_id: window.GAME_BOSS_ID, mode: 'docking_battle', difficulty: 'junior' })
            });
            const data = await resp.json();
            if (data.session) {
                this.sessionId = data.session.id;
                this.bossHP = data.session.boss_current_hp;
                this.bossInitialHP = data.session.boss_initial_hp || 300;
                this.updateHUD();
            }
        } catch (e) {
            this.log("SESSION SYNC ERROR", "#ff3e3e");
        }
    }

    renderDeckLoading() {
        const dc = document.getElementById('deckCards');
        if (!dc) return;
        const count = this.deckSize || 1;
        dc.innerHTML = Array.from({length: count}, () =>
            `<div class="mol-card loading"><div class="mol-loading-text">GENERATING...</div></div>`
        ).join('');
    }

    async fetchDeck() {
        if (!this.sessionId) return;
        try {
            const qs = this.pinnedSmiles ? `?pinned_seed=${encodeURIComponent(this.pinnedSmiles)}` : '';
            const resp = await fetch(`/api/v3/game/session/${this.sessionId}/candidates${qs}`);
            const data = await resp.json();
            if (data.candidates && data.candidates.length) {
                this.currentDeck = data.candidates;
                this.renderDeck(data.candidates);
            } else {
                this.renderFallbackDeck();
            }
        } catch (e) {
            this.renderFallbackDeck();
        }
    }

    // Replace only the slot that was consumed, keep the other cards unchanged
    async refreshOneCard(firedIdx) {
        if (!this.sessionId) return;
        try {
            const qs = this.pinnedSmiles ? `?pinned_seed=${encodeURIComponent(this.pinnedSmiles)}` : '';
            const resp = await fetch(`/api/v3/game/session/${this.sessionId}/candidates${qs}`);
            const data = await resp.json();
            if (data.candidates && data.candidates.length) {
                // Pick the first candidate that isn't already in the other deck slots
                const existingSmiles = new Set(
                    this.currentDeck.filter((_, i) => i !== firedIdx).map(c => c.smiles)
                );
                const replacement = data.candidates.find(c => !existingSmiles.has(c.smiles))
                                 || data.candidates[0];
                if (this.currentDeck[firedIdx]) {
                    this.currentDeck[firedIdx] = replacement;
                } else {
                    this.currentDeck.push(replacement);
                }
                this.renderDeck(this.currentDeck);
                // Auto-select next available card (prefer lowest index)
                const nextIdx = firedIdx === 0 && this.currentDeck.length > 1 ? 0 : Math.max(0, firedIdx - 1);
                this.selectCard(nextIdx);
            }
        } catch (e) {
            // On error keep existing deck — player can still fire other slots
        }
    }

    renderFallbackDeck() {
        const smiles = window.GAME_STARTER_SMILES || '';
        this.currentDeck = [{ smiles, name: 'SEED-1', composite: 0.4, qed: 0.4, sas: 4, lipinski: true }];
        this.renderDeck(this.currentDeck);
    }

    renderDeck(candidates) {
        const dc = document.getElementById('deckCards');
        if (!dc) return;
        dc.innerHTML = '';
        candidates = candidates.slice(0, this.deckSize || 1);
        candidates.forEach((c, i) => {
            const pct = Math.round(c.composite * 100);
            const barColor = pct >= 65 ? '#3fb950' : pct >= 50 ? '#f6ad55' : '#ff3e3e';
            const shortSmiles = c.smiles.length > 22 ? c.smiles.substring(0, 22) + '...' : c.smiles;
            const isPinned = this.pinnedSmiles === c.smiles;
            const knownPct = Math.round(this.knownScore * 100);
            const delta = pct - knownPct;
            const deltaStr = delta >= 0 ? `+${delta}% vs known` : `${delta}% vs known`;
            const deltaColor = delta >= 0 ? '#3fb950' : '#f6ad55';
            const div = document.createElement('div');
            div.className = `mol-card${i === 0 ? ' selected' : ''}`;
            div.id = `card-${i}`;
            div.innerHTML = `
                <div class="mol-card-key">[${i + 1}]</div>
                <button class="mol-card-pin${isPinned ? ' pinned' : ''}" data-idx="${i}" title="Pin as scaffold">📌</button>
                <div class="mol-card-name">${c.name}</div>
                <div class="mol-card-smiles" title="${c.smiles}">${shortSmiles}</div>
                <div class="mol-card-power">
                    <div class="power-bar" style="width:${pct}%;background:${barColor};"></div>
                </div>
                <div class="mol-card-pct" style="color:${barColor}">${pct}%</div>
                <div class="mol-card-delta" style="color:${deltaColor};font-size:0.65rem;margin-top:2px;">${deltaStr}</div>
            `;
            div.addEventListener('click', () => this.selectCard(i));
            dc.appendChild(div);
        });
        // Pin button events (stop propagation so card click isn't also triggered)
        dc.querySelectorAll('.mol-card-pin').forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                const idx = parseInt(btn.dataset.idx);
                const smiles = candidates[idx]?.smiles;
                if (this.pinnedSmiles === smiles) {
                    this.pinnedSmiles = null;
                    this.log('SCAFFOLD PIN removed', '#888');
                } else {
                    this.pinnedSmiles = smiles;
                    this.log(`SCAFFOLD PINNED: ${candidates[idx]?.name}`, '#f6ad55');
                }
                this.renderDeck(candidates);
                const bar = document.getElementById('pinnedSeedBar');
                if (bar) { bar.style.display = this.pinnedSmiles ? 'block' : 'none'; }
            });
        });
        // Update pinned-seed indicator
        let bar = document.getElementById('pinnedSeedBar');
        if (!bar) {
            bar = document.createElement('div');
            bar.id = 'pinnedSeedBar';
            bar.className = 'pinned-seed-bar';
            bar.textContent = '📌 SCAFFOLD LOCKED';
            dc.parentElement?.appendChild(bar);
        }
        bar.style.display = this.pinnedSmiles ? 'block' : 'none';
        this.selectCard(0);
    }

    selectCard(idx) {
        if (idx >= this.currentDeck.length) return;
        this.selectedCardIdx = idx;
        this.selectedSmiles = this.currentDeck[idx].smiles;
        this.selectedMolName = this.currentDeck[idx].name;
        document.querySelectorAll('.mol-card').forEach((c, i) => c.classList.toggle('selected', i === idx));
        this.log(`SELECTED: ${this.selectedMolName}`);
    }

    injectDesignedMolecule(smiles, label) {
        // Prepend the custom-designed molecule to the deck and select it
        const custom = { smiles, name: label, composite: 0, qed: 0, sas: 0, lipinski: true };
        this.currentDeck = [custom, ...this.currentDeck.slice(0, Math.max(0, (this.deckSize || 1) - 1))];
        this.renderDeck(this.currentDeck);
        // Select it immediately
        this.selectedSmiles  = smiles;
        this.selectedMolName = label;
        document.querySelectorAll('.mol-card').forEach((c, i) => c.classList.toggle('selected', i === 0));
        this.log(`🧪 CUSTOM DRUG LOADED: ${label}`, '#00f2ff');
        // Dynamic confirmation — label is unknown at preload time
        this.playTTS(`Custom drug ${label} loaded. Ready to fire!`);
    }

    setupEventListeners() {
        window.addEventListener('resize', () => {
            if (!this.container) return;
            this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        });

        window.addEventListener('keydown', e => {
            // Prevent browser scroll / default actions for all game keys
            if (['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code)) {
                e.preventDefault();
            }
            this.keys[e.code] = true;
            if (e.code === 'Space' && !e.repeat) this.onSpacebarFire();
            if (e.code === 'Digit1') this.selectCard(0);
            if (e.code === 'Digit2') this.selectCard(1);
            if (e.code === 'Digit3') this.selectCard(2);
            if (e.code === 'KeyM' && !e.repeat) audioMgr.toggleMute();
        });
        window.addEventListener('keyup', e => { this.keys[e.code] = false; });

        this.container.addEventListener('mousemove', e => this.onMouseMove(e));
        this.container.addEventListener('mousedown', () => {
            if (this.isGameOver || this.attackLocked) return;
            this.isAiming = true;
            document.getElementById('crosshair-ui')?.classList.add('aiming');
        });
        this.container.addEventListener('mouseup', () => this.onMouseUp());
        document.getElementById('biome-select')?.addEventListener('change', e => this.applyTheme(e.target.value));
        document.getElementById('diff-select')?.addEventListener('change', () => this.updateSpawnRate());
        document.getElementById('scClose')?.addEventListener('click', () => this.hideScienceCard());
        document.getElementById('btnCustomSmiles')?.addEventListener('click', () => {
            const row = document.getElementById('deckCustomRow');
            if (row) row.style.display = row.style.display === 'none' ? 'flex' : 'none';
        });
        document.getElementById('btnSetCustom')?.addEventListener('click', () => {
            const val = document.getElementById('customSmilesInput')?.value.trim();
            if (val) {
                this.selectedSmiles = val;
                this.selectedMolName = molCodename(val);
                this.log(`CUSTOM: ${this.selectedMolName}`);
                document.querySelectorAll('.mol-card').forEach(c => c.classList.remove('selected'));
                const row = document.getElementById('deckCustomRow');
                if (row) row.style.display = 'none';
            }
        });
        document.getElementById('btn-cross-validate')?.addEventListener('click', () => this.crossValidate());
        document.getElementById('btnMute')?.addEventListener('click', () => audioMgr.togglePause());

        // Leaderboard toggle
        document.getElementById('btnLeaderboard')?.addEventListener('click', () => {
            const panel = document.getElementById('leaderboardPanel');
            if (panel) panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        });
        document.getElementById('lbClose')?.addEventListener('click', () => {
            document.getElementById('leaderboardPanel').style.display = 'none';
        });

        // Notebook
        document.getElementById('btnNotebook')?.addEventListener('click', () => this.showNotebook());
        document.getElementById('btn-show-notebook')?.addEventListener('click', () => this.showNotebook());
        document.getElementById('notebookClose')?.addEventListener('click', () => {
            document.getElementById('notebookOverlay').style.display = 'none';
        });
        document.getElementById('notebookCsvBtn')?.addEventListener('click', () => this.exportNotebookCsv());

        // Docking guide resume button
        document.getElementById('dgResumeBtn')?.addEventListener('click', () => this._forceDismissGuide());

        // Weapon loadout picker (story screen)
        document.querySelectorAll('.story-weapon-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.story-weapon-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.deckSize = parseInt(btn.dataset.count, 10) || 1;
            });
        });
    }

    onSpacebarFire() {
        if (this.isGameOver || !this.gameStarted) return;
        if (this.attackLocked) { this.showLockedWarning(); return; }
        if (!this.fireReady) return;
        this.fireReady = false;
        setTimeout(() => { this.fireReady = true; }, this.fireCooldown);
        this.launchAttack();
    }

    applyTheme(themeKey) {
        const theme = THEMES[themeKey] || THEMES.jungle;
        this.renderer.setClearColor(theme.bg);
        this.scene.fog = new THREE.FogExp2(theme.fog, 0.012);
        document.getElementById('loc-name').innerText = theme.name;
        while (this.envGroup.children.length) this.envGroup.remove(this.envGroup.children[0]);
        const grid = new THREE.GridHelper(300, 50, theme.floor, theme.bg);
        grid.position.y = -5; this.envGroup.add(grid);
        for (let i = 0; i < 30; i++) {
            const sz = Math.random() * 2 + 1;
            const m = new THREE.Mesh(new THREE.ConeGeometry(0.6, sz * 3, 4),
                new THREE.MeshPhongMaterial({ color: theme.floor, emissive: theme.env, emissiveIntensity: 0.2 }));
            m.position.set((Math.random()-.5)*180, -5+sz, (Math.random()-.5)*120);
            this.envGroup.add(m);
        }
    }

    updateSpawnRate() {
        if (this.spawnTimer) clearInterval(this.spawnTimer);
        const diff = document.getElementById('diff-select')?.value || 'normal';
        this.spawnTimer = setInterval(() => this.spawnObstacle(), DIFFICULTY[diff].spawnRate);
    }

    onMouseMove(event) {
        const rect = this.container.getBoundingClientRect();
        const x = event.clientX - rect.left, y = event.clientY - rect.top;
        this.mouse.x = (x / this.container.clientWidth) * 2 - 1;
        this.mouse.y = -(y / this.container.clientHeight) * 2 + 1;
        const ch = document.getElementById('crosshair-ui');
        if (ch) { ch.style.left = x + 'px'; ch.style.top = y + 'px'; }
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
        this.raycaster.ray.intersectPlane(plane, this.targetPoint);
    }

    onMouseUp() {
        if (this.isAiming && !this.isGameOver && this.gameStarted) {
            if (this.attackLocked) this.showLockedWarning();
            else this.launchAttack();
        }
        this.isAiming = false;
        document.getElementById('crosshair-ui')?.classList.remove('aiming');
    }

    showLockedWarning() {
        // Debounce — don't spam if player holds space or clicks repeatedly
        const now = Date.now();
        if (this._lastLockedWarn && now - this._lastLockedWarn < 1200) return;
        this._lastLockedWarn = now;

        const msgs = [
            '⚠️ Missile still in flight — wait for impact!',
            '⏳ Hold on! Your molecule is still analysing.',
            '🔬 Previous shot in progress — let it finish!',
            '💥 Damage calculating — stand by!',
        ];
        const text = msgs[Math.floor(Math.random() * msgs.length)];

        // Float it near the crosshair / center-top of arena
        const div = document.createElement('div');
        div.className = 'locked-warn';
        div.textContent = text;
        this.container.appendChild(div);
        setTimeout(() => div.remove(), 1600);

        // Also pulse the analyzing badge so player notices it
        const badge = document.getElementById('analyzingOverlay');
        if (badge && badge.style.display !== 'none') {
            badge.classList.add('badge-pulse');
            setTimeout(() => badge.classList.remove('badge-pulse'), 600);
        }
    }

    async launchAttack() {
        if (!this.selectedSmiles || this.attackLocked || this.isGameOver) return;
        this.attackLocked = true;
        this._lockTimestamp = Date.now();
        this.firedCardIdx = this.selectedCardIdx;  // remember which slot was consumed

        const type = document.getElementById('missile-select')?.value || 'standard';
        const isParabolic = document.getElementById('traj-select')?.value === 'nonlinear';
        const color = type === 'hypersonic' ? 0xff00ff : 0x00f2ff;

        const body = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 1.5),
            new THREE.MeshPhongMaterial({ color, emissive: color }));
        body.rotation.x = Math.PI / 2;
        const group = new THREE.Group(); group.add(body);

        const shipX = this.playerShip ? this.playerShip.position.x : 0;
        const shipY = this.playerShip ? this.playerShip.position.y + 1 : -7;
        group.position.set(shipX, shipY, 32);
        this.scene.add(group);

        const smilesToSend = this.selectedSmiles;
        const molName = this.selectedMolName;

        const bossPos = this.monster ? this.monster.position.clone() : new THREE.Vector3(0, 5, 0);
        const proj = {
            mesh: group, t: 0,
            speed: type === 'hypersonic' ? 2.5 : 1.5,
            isParabolic,
            startPos: group.position.clone(),
            targetPos: bossPos,
            parked: false, hitTime: 0,
            apiResult: null, apiSettled: false,
            molName,
        };
        this.projectiles.push(proj);
        this.log(`FIRING: ${molName}`, "#00f2ff");

        if (this.sessionId) {
            fetch(`/api/v3/game/session/${this.sessionId}/attack`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ smiles: smilesToSend })
            }).then(r => r.json()).then(data => {
                proj.apiResult = data;
                proj.apiSettled = true;
            }).catch(() => {
                proj.apiResult = null;
                proj.apiSettled = true;
            });
        }
    }

    showAnalyzing(molName) {
        const el = document.getElementById('analyzingOverlay');
        const mn = document.getElementById('analyzingMolName');
        if (el) el.style.display = 'flex';
        if (mn) mn.textContent = molName || '';
        if (this.monster) {
            this.monster.traverse(m => {
                if (m.isMesh && m.material && m.material.emissive) m.material.emissive.setHex(0xffaa00);
            });
        }
        this.showDockingGuide(molName); // show educational guide during docking
    }

    hideAnalyzing() {
        const el = document.getElementById('analyzingOverlay');
        if (el) el.style.display = 'none';
        const profile = this.bossProfile;
        if (this.monster) {
            this.monster.traverse(m => {
                if (m.isMesh && m.material && m.material.emissive) m.material.emissive.setHex(profile.emissive || 0x000000);
            });
        }
        this.hideDockingGuide(); // hide educational guide when docking completes
    }

    applyAttackResult(data, proj) {
        this.hideAnalyzing();
        if (proj) {
            this.scene.remove(proj.mesh);
            const i = this.projectiles.indexOf(proj);
            if (i > -1) this.projectiles.splice(i, 1);
        }

        if (!data || data.error) {
            this.bossHP = Math.max(0, this.bossHP - 1);
            this.updateHUD();
            this.attackLocked = false;
            this.refreshOneCard(this.firedCardIdx ?? 0);
            this.log("API ERROR — minimal damage applied", "#ff3e3e");
            return;
        }

        const damage = data.damage || 0;
        const newHP = data.new_hp;
        const props = data.best_props || {};
        const composite = props.composite_score || 0;
        const isNewBest = data.is_new_best || false;

        this.bossHP = newHP;
        if (composite > this.bestScore) this.bestScore = composite;
        this.attackCount = data.session?.attacks_count || (this.attackCount + 1);

        // Log attack for notebook
        this.attackLog.push({ n: this.attackCount, composite, molName: proj?.molName || '?' });

        // RP earned
        if (data.rp_earned) {
            this.totalRp += data.rp_earned;
            const rpEl = document.getElementById('rp-display');
            if (rpEl) rpEl.textContent = `⭐ ${this.totalRp} RP`;
            if (data.rp_earned > 10) this.log(`+${data.rp_earned} RP earned!`, '#f5c518');
        }

        // Memory penalty note
        if (data.memory_penalty) {
            this.log('⚠️ Molecular memory penalty — try a novel scaffold!', '#888');
        }

        // Phase transition
        if (data.phase_changed && data.session) {
            const newPhase = data.session.phase ?? this.bossPhase;
            if (newPhase !== this.bossPhase) {
                this.bossPhase = newPhase;
                this.triggerPhaseTransition(newPhase, data.new_mutation);
            }
        } else if (data.new_mutation) {
            this.showMutationAlert(data.new_mutation);
        }

        if (composite >= 0.55) {
            this.comboCount++;
            this.consecutiveLowScores = 0;
        } else {
            this.comboCount = 0;
            this.consecutiveLowScores = (this.consecutiveLowScores || 0) + 1;
        }
        this.updateComboDisplay();
        this.updateBaselineStrip(composite);
        this.addJourneyDot(composite, proj?.molName || '?');
        if (composite >= this.knownScore) this.liveNoveltyCheck(data.best_smiles || '');
        this.checkAndShowHint();

        const comboDmgBonus = this.comboCount >= 3 ? 1.25 : 1;
        this.createExplosion(this.monster.position.clone(), this.bossProfile.color || 0xff3e3e, 2 * comboDmgBonus);
        this.showFloatingDamage(damage * comboDmgBonus, isNewBest, composite);
        this.updateHUD();
        this.showScienceCard(data);
        this.setBossWounded();

        if (data.won) { this.onVictory(data); return; }
        if (data.lost) {
            this.isGameOver = true;
            const r = document.getElementById('game-over-reason');
            if (r) r.textContent = 'You exhausted all attack attempts without defeating the pathogen. Try easier difficulty or a different molecule strategy.';
            document.getElementById('screen-game-over').style.display = 'flex';
            this.showPatientOutcome(false);
            if (this.outbreakTimer) clearInterval(this.outbreakTimer);
            return;
        }

        this.attackLocked = false;
        // Only replace the slot that was fired — other cards stay unchanged
        setTimeout(() => this.refreshOneCard(this.firedCardIdx ?? 0), 500);
    }

    showFloatingDamage(damage, isNewBest, composite) {
        const div = document.createElement('div');
        div.className = 'float-dmg' + (isNewBest ? ' float-dmg-best' : damage > 0 ? ' float-dmg-hit' : ' float-dmg-miss');
        const pct = composite !== undefined ? Math.round(composite * 100) : null;
        if (pct !== null) {
            const beatKnown = composite >= this.knownScore;
            div.textContent = isNewBest ? `⭐ ${pct}% binding — New Best!` : beatKnown ? `✅ ${pct}% — Beats known drug!` : `${pct}% binding`;
        } else {
            div.textContent = damage > 0 ? `${damage.toFixed(1)} pts` : 'Low binding';
        }
        const arena = this.container.getBoundingClientRect();
        div.style.left = (arena.width * 0.45 + (Math.random()-.5)*60) + 'px';
        div.style.top = (arena.height * 0.35) + 'px';
        this.container.appendChild(div);
        setTimeout(() => div.remove(), 1800);
    }

    showScienceCard(data) {
        const props = data.best_props || {};
        const composite = props.composite_score || 0;
        const qed = props.qed || 0;
        const sas = props.sas || 5;
        const lipinski = props.lipinski_pass;
        const tanimoto = props.tanimoto || 0;
        const isNewBest = data.is_new_best;

        document.getElementById('scMolName').textContent = molCodename(data.best_smiles || '');
        document.getElementById('scPowerVal').textContent = `${Math.round(composite * 100)}%`;
        document.getElementById('scPowerVal').style.color = composite >= 0.65 ? '#3fb950' : composite >= 0.5 ? '#f6ad55' : '#ff3e3e';
        document.getElementById('scQED').textContent = toStars(qed, 1);
        document.getElementById('scSAS').textContent = sasToStars(sas);
        document.getElementById('scLipinski').textContent = lipinski ? '✅ Yes' : '❌ No';

        // Contextual science message based on limiting property
        let msg = getAttackMsg(composite, window.GAME_BOSS_NAME || 'the pathogen', isNewBest);
        if (composite >= 0.40) {
            if (qed < 0.4) msg = `Low drugability score (${Math.round(qed*100)}%). Try adding a hydroxyl or amine group to improve oral bioavailability.`;
            else if (sas > 6) msg = `Synthesis score is high (${sas.toFixed(1)}). Simpler ring systems like piperidine or pyrimidine are easier to make.`;
            else if (tanimoto > 0.8) msg = `Very similar to known drugs (${Math.round(tanimoto*100)}% match). Explore different scaffolds for true novelty.`;
            else if (!lipinski) msg = `Lipinski failure — molecule may have poor oral absorption. Keep MW < 500 Da and LogP < 5.`;
        }
        document.getElementById('scMsg').textContent = msg;
        const nb = document.getElementById('scNewBest');
        if (nb) nb.style.display = isNewBest ? 'block' : 'none';

        const card = document.getElementById('scienceCard');
        if (card) card.classList.add('visible');

        if (this.scienceCardTimer) clearTimeout(this.scienceCardTimer);
        this.scienceCardTimer = setTimeout(() => this.hideScienceCard(), 7000);

        // Play the matching pre-generated hit clip
        const hitKey = composite >= 0.80 ? 'hit_perfect'
                     : composite >= 0.70 ? 'hit_excellent'
                     : composite >= 0.60 ? 'hit_good'
                     : composite >= 0.50 ? 'hit_moderate'
                     : composite >= 0.40 ? 'hit_weak'
                     : 'hit_minimal';
        audioMgr.playKey(hitKey);
    }

    hideScienceCard() {
        const card = document.getElementById('scienceCard');
        if (card) card.classList.remove('visible');
        if (this.scienceCardTimer) { clearTimeout(this.scienceCardTimer); this.scienceCardTimer = null; }
    }

    setBossWounded() {
        const hpPct = this.bossHP / (this.bossInitialHP || 300);
        if (hpPct < 0.5 && this.bossProfile.rotY) {
            this.bossProfile._rotYBoost = this.bossProfile.rotY * 0.5;
        }
        // Update phase indicator text
        const phases = ['', '⚠️ PHASE 2 — WOUNDED', '🔴 PHASE 3 — CRITICAL'];
        const pi = document.getElementById('phaseIndicator');
        if (pi && this.bossPhase > 0) {
            pi.textContent = phases[this.bossPhase] || '';
            pi.style.display = 'block';
        }
    }

    triggerPhaseTransition(newPhase, mutation) {
        const phaseTaunts = [null, window.GAME_PHASE2_TAUNT, window.GAME_PHASE3_TAUNT];
        const taunt = phaseTaunts[newPhase];
        const phaseColors = [0x000000, 0xff6600, 0xff0000];
        const phaseColor = phaseColors[newPhase] || 0xff0000;

        // Flash boss with phase colour
        if (this.monster) {
            this.monster.traverse(m => {
                if (m.isMesh && m.material?.emissive) m.material.emissive.setHex(phaseColor);
            });
            setTimeout(() => {
                this.monster?.traverse(m => {
                    if (m.isMesh && m.material?.emissive) m.material.emissive.setHex(this.bossProfile.emissive || 0);
                });
            }, 600);
        }

        // Phase banner
        const phaseLabels = ['', 'PHASE 2: WOUNDED', 'PHASE 3: CRITICAL'];
        this.log(`⚡ ${phaseLabels[newPhase] || 'NEW PHASE'} — pathogen adapting!`, '#ff6600');

        if (taunt) {
            const phaseDiv = document.createElement('div');
            phaseDiv.className = 'ff-alert';
            phaseDiv.style.cssText = 'border-color:#ff6600;color:#ff6600;text-shadow:0 0 12px #ff6600;font-size:17px;';
            phaseDiv.textContent = `💀 ${taunt}`;
            this.container.appendChild(phaseDiv);
            setTimeout(() => phaseDiv.remove(), 3500);
            // Play pre-generated phase taunt
            const phaseKey = newPhase === 1 ? 'phase2' : 'phase3';
            setTimeout(() => audioMgr.playKey(phaseKey), 800);
        }

        if (mutation) this.showMutationAlert(mutation);
    }

    showMutationAlert(mutation) {
        const el = document.getElementById('mutationAlert');
        if (!el) return;
        document.getElementById('mutAlertIcon').textContent = mutation.icon || '🧬';
        document.getElementById('mutAlertName').textContent = mutation.name || 'Unknown Mutation';
        document.getElementById('mutAlertDesc').textContent = mutation.description || '';
        el.style.display = 'flex';
        this.log(`🧬 MUTATION: ${mutation.name}`, '#ff3e3e');
        setTimeout(() => { el.style.display = 'none'; }, 4500);
        // Play pre-generated mutation clip, fall back to dynamic TTS
        const mutKey = `mut_${mutation.id}`;
        if (audioMgr.cache[mutKey]) audioMgr.playKey(mutKey);
        else this.playTTS(`Warning! Pathogen mutation: ${mutation.name}. ${(mutation.description||'').substring(0,100)}`);
    }

    startOutbreakTimer() {
        const el = document.getElementById('outbreak-timer');
        if (el) el.style.display = 'block';
        this.outbreakTimer = setInterval(() => {
            this.outbreakTimeLeft--;
            const m = Math.floor(this.outbreakTimeLeft / 60);
            const s = String(this.outbreakTimeLeft % 60).padStart(2, '0');
            if (el) {
                el.textContent = `⏱ ${m}:${s}`;
                if (this.outbreakTimeLeft <= 60) el.classList.add('critical');
            }
            // Escalate spore rate every 2 minutes
            if (this.outbreakTimeLeft % 120 === 0 && this.outbreakTimeLeft > 0) {
                this.log('🦠 OUTBREAK ESCALATING — spore pressure rising!', '#ff3e3e');
                const diff = document.getElementById('diff-select')?.value || 'normal';
                const baseRate = DIFFICULTY[diff]?.spawnRate || 4000;
                const escalation = Math.max(1200, baseRate - ((480 - this.outbreakTimeLeft) / 120) * 600);
                if (this.spawnTimer) clearInterval(this.spawnTimer);
                this.spawnTimer = setInterval(() => this.spawnObstacle(), escalation);
            }
            if (this.outbreakTimeLeft <= 0) {
                clearInterval(this.outbreakTimer);
                if (!this.isGameOver) {
                    this.isGameOver = true;
                    const r = document.getElementById('game-over-reason');
                    if (r) r.textContent = 'The outbreak window closed. The pathogen spread beyond containment.';
                    document.getElementById('screen-game-over').style.display = 'flex';
                    this.showPatientOutcome(false);
                }
            }
        }, 1000);
    }

    async loadLeaderboard() {
        try {
            const resp = await fetch(`/api/v3/game/leaderboard/${window.GAME_BOSS_ID}`);
            const entries = await resp.json();
            const list = document.getElementById('lbList');
            if (!list) return;
            if (!entries.length) { list.innerHTML = '<div style="opacity:0.5;font-size:10px;padding:8px;">No entries yet — be first!</div>'; return; }
            list.innerHTML = entries.slice(0, 8).map((e, i) => {
                const rankClass = i === 0 ? 'top1' : i === 1 ? 'top2' : i === 2 ? 'top3' : '';
                const name = (e.username || 'Scientist').substring(0, 12);
                const pct = Math.round((e.best_score || 0) * 100);
                return `<div class="lb-entry"><span class="lb-rank ${rankClass}">${i+1}</span><span class="lb-name">${name}</span><span class="lb-score">${pct}%</span></div>`;
            }).join('');
        } catch (e) { /* leaderboard unavailable — silent */ }
    }

    showNotebook() {
        const overlay = document.getElementById('notebookOverlay');
        if (!overlay) return;
        overlay.style.display = 'flex';

        const canvas = document.getElementById('notebookChart');
        if (!canvas || !window.Chart || !this.attackLog.length) return;

        // Destroy previous chart instance if exists
        if (this._notebookChart) { this._notebookChart.destroy(); this._notebookChart = null; }

        const labels = this.attackLog.map(a => `#${a.n}`);
        const scores = this.attackLog.map(a => Math.round(a.composite * 100));
        const colors = scores.map(s => s >= 65 ? '#3fb950' : s >= 50 ? '#f6ad55' : '#ff3e3e');

        this._notebookChart = new Chart(canvas, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Composite Score',
                    data: this.attackLog.map((a, i) => ({ x: i + 1, y: Math.round(a.composite * 100) })),
                    pointBackgroundColor: colors,
                    pointBorderColor: colors,
                    pointRadius: 6,
                    showLine: true,
                    borderColor: 'rgba(0,242,255,0.3)',
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                const a = this.attackLog[ctx.dataIndex];
                                return `${a.molName}: ${Math.round(a.composite*100)}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Attack #', color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { title: { display: true, text: 'Score (%)', color: '#888' }, ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' }, min: 0, max: 100,
                         annotations: { winLine: { type: 'line', yMin: Math.round(this.winThreshold*100), yMax: Math.round(this.winThreshold*100), borderColor: '#3fb950', borderWidth: 1, label: { content: 'Win threshold', display: true } } }
                    }
                },
                backgroundColor: 'transparent',
            }
        });

        // Summary stats
        const best = Math.max(...scores);
        const avg = Math.round(scores.reduce((a,b)=>a+b,0)/scores.length);
        const statsEl = document.getElementById('notebookStats');
        if (statsEl) statsEl.textContent = `${this.attackLog.length} attacks · Best: ${best}% · Avg: ${avg}%`;

        // Threshold line annotation fallback
        if (canvas.getContext) {
            // Draw win threshold line via afterDraw plugin workaround — skip if chartjs-plugin-annotation not loaded
        }
    }

    exportNotebookCsv() {
        const rows = ['Attack,Molecule,Score_%'];
        this.attackLog.forEach(a => rows.push(`${a.n},"${a.molName}",${Math.round(a.composite*100)}`));
        const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `pathohunt_${window.GAME_BOSS_ID}_notebook.csv`;
        a.click(); URL.revokeObjectURL(url);
    }

    showPatientOutcome(won) {
        const ps = window.GAME_PATIENT_STORY || {};
        const text = won ? ps.outcome_win : ps.outcome_loss;
        if (!text) return;
        const id = won ? 'patient-outcome-win' : 'patient-outcome-loss';
        const el = document.getElementById(id);
        if (el) { el.innerHTML = `<strong>${ps.name || 'Patient'}:</strong> ${text}`; el.style.display = 'block'; }
        if (text) setTimeout(() => audioMgr.playKey(won ? 'patient_win' : 'patient_loss'), 3000);
    }

    updateWinMarker() {
        const marker = document.getElementById('win-threshold-marker');
        if (marker) marker.style.left = `${this.winThreshold * 100}%`;
    }

    updateHUD() {
        const initHP = this.bossInitialHP || 300;
        const bossHpPct = Math.max(0, this.bossHP / initHP * 100);
        document.getElementById('enemy-hp-fill').style.width = `${bossHpPct}%`;
        document.getElementById('enemy-hp-text').innerText = `${this.bossHP.toFixed(1)} HP`;
        document.getElementById('player-hp-fill').style.width = `${this.playerHP / 10}%`;
        document.getElementById('player-hp-text').innerText = `${this.playerHP} / 1000`;
        const bsPct = Math.min(100, this.bestScore / Math.max(this.winThreshold, 0.01) * 100);
        document.getElementById('best-score-fill').style.width = `${bsPct}%`;
        document.getElementById('best-score-text').textContent = `${Math.round(this.bestScore * 100)}%`;
        const ac = document.getElementById('attack-counter');
        if (ac) ac.textContent = `ATTACKS: ${this.attackCount}`;
        // Winning badge: show when bestScore beats known drug baseline
        const wb = document.getElementById('winningBadge');
        if (wb) wb.style.display = (this.bestScore >= this.knownScore && !this.isGameOver) ? 'block' : 'none';
        // Keep baseline strip known drug label current
        const bsKnownEl = document.getElementById('bs-known-pct');
        if (bsKnownEl) bsKnownEl.textContent = Math.round(this.knownScore * 100) + '%';
    }

    log(msg, color) {
        color = color || "#00f2ff";
        const c = document.getElementById('combat-log');
        if (!c) return;
        const d = document.createElement('div');
        d.className = 'log-entry';
        d.style.cssText = `color:${color};border-color:${color}`;
        d.innerHTML = "> " + msg;
        c.prepend(d);
        while (c.children.length > 6) c.lastChild.remove();
    }

    async playTTS(text) {
        try {
            const r = await fetch('/api/v3/game/tts', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text.substring(0, 200) })
            });
            const blob = await r.blob();
            audioMgr.play(blob);
        } catch (e) {}
    }

    setAnalyzingPhase(line1, line2) {
        const el = document.getElementById('analyzingText');
        const el2 = document.getElementById('analyzingMolName');
        if (el) el.textContent = line1 || 'ANALYZING MOLECULAR IMPACT';
        if (el2) el2.textContent = line2 || '';
        // advance guide phase indicator
        if (line1.includes('MEMBRANE')) this.setDockingGuideStep(0);
        else if (line1.includes('BINDING')) this.setDockingGuideStep(1);
        else if (line1.includes('DOCKING')) this.setDockingGuideStep(2);
    }

    // ── Docking education guide ───────────────────────────────────
    showDockingGuide(molName) {
        const el = document.getElementById('dockingGuide');
        if (!el) return;
        const fact = DOCKING_FACTS[Math.floor(Math.random() * DOCKING_FACTS.length)];
        const set = (id, val) => { const n = document.getElementById(id); if (n) n.textContent = val; };
        set('dgMolLabel',  molName || '–');
        set('dgFactTitle', fact.title);
        set('dgFactBody',  fact.body);
        set('dgTermName',  fact.term);
        set('dgTermDef',   fact.def);
        document.querySelectorAll('.dg-phase-step').forEach(s => s.classList.remove('active', 'done'));
        const fill = document.getElementById('dgProgressFill');
        if (fill) fill.style.width = '0%';
        el.style.display = 'flex';
        el.classList.remove('dg-exit');
        // animate progress bar over ~3 s (matches docking phase duration)
        this._dgStart = Date.now();
        if (this._dgRaf) cancelAnimationFrame(this._dgRaf);
        const tick = () => {
            if (!this._dgStart) return;
            const pct = Math.min(95, ((Date.now() - this._dgStart) / 3200) * 100);
            if (fill) fill.style.width = pct + '%';
            if (pct < 95) this._dgRaf = requestAnimationFrame(tick);
        };
        this._dgRaf = requestAnimationFrame(tick);
    }

    hideDockingGuide() {
        if (this._dgRaf) { cancelAnimationFrame(this._dgRaf); this._dgRaf = null; }
        this._dgStart = null;
        const el = document.getElementById('dockingGuide');
        if (!el || el.style.display === 'none') return;
        const fill = document.getElementById('dgProgressFill');
        if (fill) fill.style.width = '100%';
        // Mark all phase steps done
        document.querySelectorAll('.dg-phase-step').forEach(s => { s.classList.remove('active'); s.classList.add('done'); });
        // Transition to post-docking "resume" state — let user finish reading
        el.classList.add('dg-complete');
        const waitHint = document.getElementById('dgWaitHint');
        const completeHint = document.getElementById('dgCompleteHint');
        const resumeBtn = document.getElementById('dgResumeBtn');
        if (waitHint) waitHint.style.display = 'none';
        if (completeHint) completeHint.style.display = '';
        if (resumeBtn) resumeBtn.style.display = '';
        // Auto-dismiss after 8 s if user doesn't click
        if (this._dgAutoDismiss) clearTimeout(this._dgAutoDismiss);
        this._dgAutoDismiss = setTimeout(() => this._forceDismissGuide(), 8000);
    }

    _forceDismissGuide() {
        if (this._dgAutoDismiss) { clearTimeout(this._dgAutoDismiss); this._dgAutoDismiss = null; }
        const el = document.getElementById('dockingGuide');
        if (!el || el.style.display === 'none') return;
        el.classList.remove('dg-complete');
        const waitHint = document.getElementById('dgWaitHint');
        const completeHint = document.getElementById('dgCompleteHint');
        const resumeBtn = document.getElementById('dgResumeBtn');
        if (waitHint) waitHint.style.display = '';
        if (completeHint) completeHint.style.display = 'none';
        if (resumeBtn) resumeBtn.style.display = 'none';
        el.classList.add('dg-exit');
        setTimeout(() => { el.style.display = 'none'; el.classList.remove('dg-exit'); }, 380);
    }

    setDockingGuideStep(step) {
        document.querySelectorAll('.dg-phase-step').forEach((el, i) => {
            el.classList.toggle('done',   i < step);
            el.classList.toggle('active', i === step);
        });
    }
    // ─────────────────────────────────────────────────────────────

    spawnObstacle() {
        if (this.isGameOver || !this.gameStarted) return;
        const diff = document.getElementById('diff-select')?.value || 'normal';
        const s = DIFFICULTY[diff];
        const isLarge = Math.random() > 0.8;
        const size = isLarge ? 3 : 1.2;
        const sporeColor = this.bossProfile.sporeColor || 0xff3e3e;
        const mesh = new THREE.Mesh(
            isLarge ? new THREE.IcosahedronGeometry(size, 1) : new THREE.OctahedronGeometry(size, 0),
            new THREE.MeshPhongMaterial({ color: sporeColor, wireframe: true, emissive: 0x110000 })
        );
        mesh.position.set((Math.random()-.5)*100, Math.random()*30, -50);
        const spd = s.speedMin + Math.random() * (s.speedMax - s.speedMin);
        mesh.velocity = new THREE.Vector3((this.camera.position.x-mesh.position.x)*0.003, (this.camera.position.y-mesh.position.y)*0.003, spd);
        mesh.health = isLarge ? s.largeHealth : 1;
        mesh.damage = isLarge ? s.largeDmg : s.smallDmg;
        mesh.isLarge = isLarge;
        this.scene.add(mesh);
        this.obstacles.push(mesh);
    }

    createExplosion(pos, color, size) {
        size = size || 1;
        const g = new THREE.Group(); g.position.copy(pos); this.scene.add(g);
        for (let i = 0; i < 20 * size; i++) {
            const p = new THREE.Mesh(new THREE.BoxGeometry(0.2,0.2,0.2), new THREE.MeshBasicMaterial({ color }));
            p.velocity = new THREE.Vector3((Math.random()-.5)*size, (Math.random()-.5)*size, (Math.random()-.5)*size);
            g.add(p);
        }
        this.explosions.push({ group: g, life: 1.0 });
    }

    takeDamage(val) {
        const prevHP = this.playerHP;
        this.playerHP = Math.max(0, this.playerHP - val);
        const vd = document.getElementById('vfx-damage');
        if (vd) { vd.style.opacity = 0.5; setTimeout(() => vd.style.opacity = 0, 150); }
        this.updateHUD();

        // Low HP warnings at thresholds (spoken once per threshold)
        if (!this._warned300 && prevHP > 300 && this.playerHP <= 300) {
            this._warned300 = true;
            this.log('⚠️ WARNING: Host defences critical! Destroy the pathogen fast!', '#ff3e3e');
            audioMgr.playKey('warn_300');
        }
        if (!this._warned150 && prevHP > 150 && this.playerHP <= 150) {
            this._warned150 = true;
            this.log('🚨 CRITICAL: Immune collapse imminent!', '#ff0000');
            audioMgr.playKey('warn_150');
        }

        if (this.playerHP <= 0 && !this.isGameOver) {
            this.isGameOver = true;
            document.getElementById('screen-game-over').style.display = 'flex';
        }
    }

    async onVictory(result) {
        this.isGameOver = true;
        this.wonMolecule = { smiles: result.best_smiles, tanimoto: result.best_props?.tanimoto || 0 };
        // Hide winning badge now that game is over
        const wb = document.getElementById('winningBadge');
        if (wb) wb.style.display = 'none';
        // Flash the screen green before showing victory
        const flash = document.getElementById('victoryFlash');
        if (flash) {
            flash.style.transition = 'opacity 0.15s ease-in';
            flash.style.opacity = '0.45';
            setTimeout(() => { flash.style.transition = 'opacity 0.6s ease-out'; flash.style.opacity = '0'; }, 200);
        }
        await new Promise(r => setTimeout(r, 320));
        document.getElementById('screen-victory').style.display = 'flex';
        document.getElementById('win-smiles').innerText = result.best_smiles || '–';

        const knownPct = Math.round((window.GAME_KNOWN_SCORE || 0.60) * 100);
        const bestPct = Math.round((result.session?.best_score || this.bestScore) * 100);
        const diff = bestPct - knownPct;

        document.getElementById('score-comparison').innerHTML = `
            <div style="display:flex;justify-content:space-between;gap:20px;margin-bottom:10px;">
                <div style="text-align:center;flex:1">
                    <div style="font-size:0.75rem;color:#888;margin-bottom:4px;">YOUR BEST</div>
                    <div style="font-size:1.6rem;font-weight:900;color:${diff>=0?'#3fb950':'#f6ad55'}">${bestPct}%</div>
                </div>
                <div style="text-align:center;flex:1">
                    <div style="font-size:0.75rem;color:#888;margin-bottom:4px;">KNOWN DRUG</div>
                    <div style="font-size:1.6rem;font-weight:900;color:#888">${knownPct}%</div>
                </div>
            </div>
            <div style="color:${diff>=0?'#3fb950':'#f6ad55'};font-weight:700;">
                ${diff>=0?`+${diff}% better than the known drug! 🎉`:`${Math.abs(diff)}% below the known drug — great learning!`}
            </div>
        `;
        document.getElementById('session-stats').innerHTML = `
            <span>⚔️ ${result.session?.attacks_count || this.attackCount} attacks</span>
            <span>🏆 Best: ${bestPct}%</span>
        `;
        this.playTTS(`Great job! By defeating the pathogen, you discovered a novel drug candidate scoring ${bestPct} percent. That's ${diff >= 0 ? 'better than' : 'close to'} the known drug!`);
        this.showPatientOutcome(true);
        const nbBtn = document.getElementById('btnNotebook');
        if (nbBtn) nbBtn.style.display = 'inline-block';
        if (this.outbreakTimer) clearInterval(this.outbreakTimer);
    }

    async crossValidate() {
        if (!this.wonMolecule?.smiles) return;
        const btn = document.getElementById('btn-cross-validate');
        const results = document.getElementById('enrich-results');
        const status = document.getElementById('novelty-status');
        btn.disabled = true; btn.innerText = "Querying ChEMBL...";
        results.style.display = 'block';
        results.innerHTML = `<p style="color:#888">Searching ChEMBL database for similar compounds...</p>`;
        try {
            const resp = await fetch('/api/v3/game/validate', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ smiles: this.wonMolecule.smiles })
            });
            const data = await resp.json();
            status.innerText = data.novel ? "NOVEL CANDIDATE" : "KNOWN ANALOG FOUND";
            status.className = `novelty-badge ${data.novel ? 'badge-novel' : 'badge-existing'}`;
            if (data.hits && data.hits.length) {
                results.innerHTML = `<p style="color:#888;margin-bottom:8px;">${data.reason}</p>` +
                    data.hits.map(h => `<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:0.82rem;">
                        <span style="color:#00f2ff;font-weight:700">${h.chembl_id}</span> — ${h.name} — <span style="color:#f6ad55">${h.similarity}% similar</span>
                    </div>`).join('');
            } else {
                results.innerHTML = `<p style="color:#3fb950">${data.reason}</p>`;
            }
        } catch(e) {
            results.innerHTML = `<p style="color:#888">ChEMBL query unavailable.</p>`;
        }
        btn.innerText = "Validated ✓";
    }

    updateBaselineStrip(composite) {
        const strip = document.getElementById('baselineStrip');
        if (!strip) return;
        const bestPct = Math.round(this.bestScore * 100);
        const knownPct = Math.round(this.knownScore * 100);
        const delta = bestPct - knownPct;
        const bestEl = document.getElementById('bs-best-pct');
        const deltaEl = document.getElementById('bs-delta');
        if (bestEl) bestEl.textContent = bestPct + '%';
        if (deltaEl) {
            if (bestPct > 0) {
                deltaEl.style.display = '';
                deltaEl.textContent = delta >= 0 ? `(+${delta}% ahead!)` : `(${delta}% to go)`;
                deltaEl.style.color = delta >= 0 ? '#3fb950' : '#f6ad55';
            } else {
                deltaEl.style.display = 'none';
            }
        }
    }

    addJourneyDot(composite, molName) {
        this.journeyDots.push({ composite, molName });
        const container = document.getElementById('journeyDots');
        if (!container) return;
        const dot = document.createElement('div');
        dot.className = 'journey-dot';
        const pct = composite * 100;
        dot.style.background = pct >= 65 ? '#3fb950' : pct >= 50 ? '#f6ad55' : '#ff4d4d';
        dot.title = `${molName}: ${Math.round(pct)}%`;
        // Scale dot slightly larger for new best
        if (composite >= this.bestScore) dot.style.transform = 'scale(1.4)';
        container.appendChild(dot);
        // Keep last 20 dots visible
        while (container.children.length > 20) container.firstChild.remove();
    }

    async liveNoveltyCheck(smiles) {
        if (!smiles) return;
        const iconEl = document.getElementById('dgNoveltyIcon');
        const textEl = document.getElementById('dgNoveltyText');
        const checkEl = document.getElementById('dgNoveltyCheck');
        if (checkEl) checkEl.style.display = 'flex';
        if (iconEl) iconEl.textContent = '🔍';
        if (textEl) textEl.textContent = 'Checking ChEMBL for known analogs…';
        try {
            const resp = await fetch('/api/v3/game/validate', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ smiles })
            });
            const data = await resp.json();
            if (iconEl) iconEl.textContent = data.novel ? '✅' : '⚠️';
            if (textEl) textEl.textContent = data.novel ? 'Novel candidate — not in ChEMBL!' : 'Similar to known compound in ChEMBL';
        } catch (_) {
            if (checkEl) checkEl.style.display = 'none';
        }
    }

    checkAndShowHint() {
        if ((this.consecutiveLowScores || 0) < 3) return;
        const hints = [
            'Tip: Add a hydroxyl (-OH) group to improve QED drugability score.',
            'Tip: Try a piperidine ring — simpler to synthesize and often better binding.',
            'Tip: Keep molecular weight under 400 Da for better oral absorption.',
            'Tip: A pyrimidine core often fits kinase binding pockets well.',
            'Tip: Reduce rotatable bonds below 10 for better binding entropy.',
        ];
        const hint = hints[Math.floor(Math.random() * hints.length)];
        this.log(`💡 ${hint}`, '#a78bfa');
        this.consecutiveLowScores = 0;
    }

    animateBoss(t) {
        if (!this.monster) return;
        const p = this.bossProfile;
        this.monster.rotation.y += (p.rotY || 0.015) + (p._rotYBoost || 0);
        this.monster.rotation.x += (p.rotX || 0.005);

        // Random wandering + evasion movement
        if (this.gameStarted) {
            if (t * 1000 > this.bossMoveTimer && !this.bossEvasionMode) {
                this.bossMoveTimer = t * 1000 + 1500 + Math.random() * 2000;
                this.bossTargetX = (Math.random() - 0.5) * 30;
                this.bossTargetY = 2 + Math.random() * 10;
            }
            // Evasion uses much faster lerp; normal wandering is also snappier
            const lerpSpeed = this.bossEvasionMode ? 0.10 : 0.032;
            this.monster.position.x += (this.bossTargetX - this.monster.position.x) * lerpSpeed;
            this.monster.position.y += (this.bossTargetY - this.monster.position.y) * lerpSpeed;
        }

        switch (p.idleAnim) {
            case 'pulse': {
                const sc = 1 + Math.sin(t * 2) * 0.04;
                this.monster.scale.setScalar(sc);
                break;
            }
            case 'twitch':
                if (Math.random() < 0.03) {
                    this.monster.position.x += (Math.random()-.5) * 0.8;
                    this.monster.position.y += (Math.random()-.5) * 0.5;
                }
                break;
            case 'float':
                this.monster.position.y += Math.sin(t * 0.7) * 0.015;
                break;
            case 'timer':
                if (this.monster.userData.orbs) {
                    this.monster.userData.orbs.forEach(o => {
                        o.angle += o.speed;
                        o.mesh.position.x = Math.cos(o.angle) * 7;
                        o.mesh.position.z = Math.sin(o.angle) * 7;
                    });
                }
                break;
        }
        const hpPct = this.bossHP / (this.bossInitialHP || 300);
        if (hpPct < 0.25) this.monster.visible = Math.random() > 0.08;
    }

    animate() {
        if (this.isGameOver) { this.renderer.render(this.scene, this.camera); return; }
        requestAnimationFrame(() => this.animate());

        const now = Date.now();
        const dt = Math.min((now - this.lastFrameTime) / 1000, 0.05);
        this.lastFrameTime = now;
        const t = now / 1000;

        // Safety: auto-unlock if attackLocked for > 35s (network/state hang)
        if (this.attackLocked && this._lockTimestamp && (now - this._lockTimestamp) > 35000) {
            this.attackLocked = false;
            this._lockTimestamp = null;
            this.hideAnalyzing();
            this.log('SYSTEM: attack lock expired — ready to fire', '#555');
            this.refreshOneCard(this.firedCardIdx ?? 0);
        }

        // Arrow key ship movement — full 2D (left/right + up/down)
        if (this.gameStarted && this.playerShip) {
            const shipSpeed = 22;
            if (this.keys['ArrowLeft'])  this.playerShipX = Math.max(-22, this.playerShipX - shipSpeed * dt);
            if (this.keys['ArrowRight']) this.playerShipX = Math.min(22,  this.playerShipX + shipSpeed * dt);
            if (this.keys['ArrowUp'])    this.playerShipY = Math.min(-2,  this.playerShipY + shipSpeed * dt);
            if (this.keys['ArrowDown'])  this.playerShipY = Math.max(-14, this.playerShipY - shipSpeed * dt);
            this.playerShip.position.x += (this.playerShipX - this.playerShip.position.x) * 0.18;
            this.playerShip.position.y += (this.playerShipY - this.playerShip.position.y) * 0.18;
            this.playerShip.rotation.z = -(this.playerShipX - this.playerShip.position.x) * 0.12;
            this.playerShip.rotation.x =  (this.playerShipY - this.playerShip.position.y) * 0.06;
            // Thruster pulse
            if (this.playerShip.userData.thruster) {
                const intensity = 0.4 + Math.sin(t * 12) * 0.3;
                this.playerShip.userData.thruster.material.emissiveIntensity = intensity;
            }
        }

        // Boss slowly advances toward camera when HP drops below 50% — pressure mechanic
        if (this.gameStarted && this.monster && this.bossInitialHP) {
            const hpRatio = this.bossHP / this.bossInitialHP;
            if (hpRatio < 0.5) {
                const advanceTarget = 5 + (0.5 - hpRatio) * 40; // z: 5 → 25 as HP drains
                this.monster.position.z += (advanceTarget - this.monster.position.z) * 0.005 * dt;
            }
        }

        this.animateBoss(t);

        // Safe object movement and pulsing
        for (let i = this.safeObjects.length - 1; i >= 0; i--) {
            const safe = this.safeObjects[i];
            safe.position.add(safe.userData.velocity);
            safe.userData.pulseT += 0.06;
            const pulse = 1 + Math.sin(safe.userData.pulseT) * 0.12;
            safe.scale.setScalar(pulse);
            safe.rotation.y += 0.025;
            safe.rotation.x += 0.012;
            // Gentle float side-to-side
            safe.userData.velocity.y = Math.sin(t * 1.2 + i) * 0.015;
            if (safe.position.z > this.camera.position.z + 5) {
                this.scene.remove(safe);
                this.safeObjects.splice(i, 1);
            }
        }

        // Projectile loop
        for (let i = this.projectiles.length - 1; i >= 0; i--) {
            const p = this.projectiles[i];
            if (p.parked) {
                const elapsed = Date.now() - p.hitTime;
                p.mesh.position.x = this.monster.position.x + Math.cos(t * 4 + i) * 2;
                p.mesh.position.y = this.monster.position.y + Math.sin(t * 4 + i) * 2;

                if (!p.phase1 && elapsed > 400) {
                    p.phase1 = true;
                    const fake = Math.round(10 + Math.random() * 22);
                    this.log(`MEMBRANE: ${fake}% — surface probe`, '#334455');
                    this.setAnalyzingPhase(`MEMBRANE: ${fake}%`, p.molName);
                }
                if (!p.phase2 && elapsed > 1200) {
                    p.phase2 = true;
                    const fake = Math.round(28 + Math.random() * 28);
                    this.log(`BINDING: ${fake}% — active site`, '#445533');
                    this.setAnalyzingPhase(`BINDING: ${fake}%`, p.molName);
                }
                if (!p.phase3 && elapsed > 2200) {
                    p.phase3 = true;
                    this.setAnalyzingPhase('DOCKING…', p.molName);
                }
                // Apply result as soon as phase3 done AND API responded
                if (p.phase3 && p.apiSettled) {
                    this.applyAttackResult(p.apiResult, p);
                } else if (elapsed > 25000) {
                    // Hard timeout — LLM can take 10-20s on busy GPU; 25s gives it room
                    this.applyAttackResult(null, p);
                }
                continue;
            }

            // Target is LOCKED at fire time — no homing
            p.t += 0.01 * p.speed;
            const tClamped = Math.min(p.t, 1);
            const nextPos = new THREE.Vector3().lerpVectors(p.startPos, p.targetPos, tClamped);
            if (p.isParabolic) nextPos.y += Math.sin(tClamped * Math.PI) * 12;
            p.mesh.lookAt(nextPos); p.mesh.position.copy(nextPos);

            // Trigger boss dodge when projectile gets close enough (one check per projectile)
            if (!p.dodgeChecked && p.mesh.position.distanceTo(this.monster.position) < 22) {
                p.dodgeChecked = true;
                const diff = document.getElementById('diff-select')?.value || 'normal';
                const dodgeChance = diff === 'hard' ? 0.55 : diff === 'easy' ? 0.20 : 0.35;
                const hpRatio = this.bossHP / (this.bossInitialHP || 300);
                const finalChance = dodgeChance + (hpRatio < 0.5 ? 0.15 : 0);
                if (!this.dodgeCooldown && Math.random() < finalChance) {
                    this.triggerDodge();
                }
            }

            // ── Collision checks run BEFORE t>=1.0 so they are never skipped ──

            // Friendly fire: safe green cell hit
            let hitSomething = false;
            for (let si = this.safeObjects.length - 1; si >= 0; si--) {
                const safe = this.safeObjects[si];
                if (p.mesh.position.distanceTo(safe.position) < 5) {
                    this.createExplosion(safe.position.clone(), 0x00ff88, 1.2);
                    this.scene.remove(safe);
                    this.safeObjects.splice(si, 1);
                    this.scene.remove(p.mesh);
                    this.projectiles.splice(i, 1);
                    this.friendlyFire();
                    hitSomething = true;
                    break;
                }
            }
            if (hitSomething) continue;

            // Enemy spore hit — molecule blocked, unlock attack so player can fire again
            for (let oi = this.obstacles.length - 1; oi >= 0; oi--) {
                const obs = this.obstacles[oi];
                if (p.mesh.position.distanceTo(obs.position) < (obs.isLarge ? 7 : 5)) {
                    obs.health--;
                    if (obs.health <= 0) { this.createExplosion(obs.position, 0x00f2ff, 1.5); this.scene.remove(obs); this.obstacles.splice(oi, 1); }
                    this.scene.remove(p.mesh); this.projectiles.splice(i, 1);
                    this.attackLocked = false;
                    // Molecule destroyed by spore — replace only that slot
                    setTimeout(() => this.refreshOneCard(this.firedCardIdx ?? 0), 300);
                    this.log('BLOCKED by enemy spore! Fire again.', '#ff6600');
                    hitSomething = true; break;
                }
            }
            if (hitSomething) continue;

            // Hit detection: projectile reached its locked target zone
            if (p.t >= 1.0) {
                const distToBoss = p.mesh.position.distanceTo(this.monster.position);
                if (distToBoss < 9) {
                    p.parked = true; p.hitTime = Date.now();
                    this.showAnalyzing(p.molName);
                } else {
                    this.onProjectileMiss(p, i);
                }
                continue;
            }

            // Park early if projectile drifts very close to boss mid-flight
            if (p.t < 0.95 && p.mesh.position.distanceTo(this.monster.position) < 6) {
                p.parked = true; p.hitTime = Date.now();
                this.showAnalyzing(p.molName);
                continue;
            }

            if (p.t > 1.8) { this.onProjectileMiss(p, i); }
        }

        // Enemy spores move toward player
        for (let i = this.obstacles.length - 1; i >= 0; i--) {
            const obs = this.obstacles[i];
            obs.position.add(obs.velocity);
            obs.rotation.x += 0.03;
            obs.rotation.y += 0.02;
            if (obs.position.z > this.camera.position.z - 5) {
                this.takeDamage(obs.damage); this.scene.remove(obs); this.obstacles.splice(i, 1);
            }
        }

        for (let i = this.explosions.length - 1; i >= 0; i--) {
            const ex = this.explosions[i];
            ex.life -= 0.03;
            ex.group.children.forEach(pp => pp.position.add(pp.velocity));
            if (ex.life <= 0) { this.scene.remove(ex.group); this.explosions.splice(i, 1); }
        }

        this.renderer.render(this.scene, this.camera);
    }
}

document.addEventListener('DOMContentLoaded', () => { window.pathoHunt3D = new PathoHunt3D(); });
