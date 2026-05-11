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
    easy:   { speedMin: 0.015, speedMax: 0.04,  smallDmg: 15,  largeDmg: 30,  largeHealth: 1, spawnRate: 5000 },
    normal: { speedMin: 0.06,  speedMax: 0.15,  smallDmg: 30,  largeDmg: 60,  largeHealth: 2, spawnRate: 3500 },
    hard:   { speedMin: 0.25,  speedMax: 0.5,   smallDmg: 60,  largeDmg: 120, largeHealth: 3, spawnRate: 2000 },
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
        this.bossHP = window.GAME_INITIAL_HP || 100;
        this.playerHP = 1000;
        this.sessionId = null;
        this.isGameOver = false;
        this.attackLocked = false;
        this.currentDeck = [];
        this.selectedCardIdx = 0;
        this.selectedSmiles = window.GAME_STARTER_SMILES || '';
        this.selectedMolName = 'SEED';
        this.bestScore = 0;
        this.winThreshold = window.GAME_WIN_THRESHOLD || 0.70;
        this.attackCount = 0;
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
        this.showStoryScreen();
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

        const nameEl = document.getElementById('storyBossName');
        const emojiEl = document.getElementById('storyBossEmoji');
        const textEl = document.getElementById('storyText');
        const winEl = document.getElementById('storyWinPct');
        if (nameEl) nameEl.textContent = window.GAME_BOSS_NAME || window.GAME_BOSS_ID;
        if (emojiEl) emojiEl.textContent = window.GAME_BOSS_EMOJI || '🦠';
        if (textEl) textEl.textContent = window.GAME_PLAIN_ENGLISH || window.GAME_BOSS_FLAVOR || 'A dangerous pathogen is threatening the host. Your mission: design molecules that block its key proteins. Good luck, Scientist.';
        if (winEl) winEl.textContent = Math.round((this.winThreshold || 0.70) * 100) + '%';

        overlay.style.display = 'flex';

        const startBtn = document.getElementById('storyStartBtn');
        if (startBtn) {
            startBtn.addEventListener('click', () => {
                overlay.style.display = 'none';
                this.startBattle();
            });
        }
        const introText = window.GAME_PLAIN_ENGLISH || window.GAME_BOSS_FLAVOR || '';
        if (introText) this.playTTS(introText.substring(0, 300));
    }

    startBattle() {
        this.gameStarted = true;
        this.updateSpawnRate();
        this.startSafeSpawner();
        this.renderDeckLoading();
        this.fetchDeck();
        this.updateWinMarker();
        this.log(`MISSION STARTED — TARGET: ${window.GAME_BOSS_NAME || window.GAME_BOSS_ID}`);
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

        setTimeout(() => this.fetchDeck(), 300);
    }

    updateComboDisplay() {
        const badge = document.getElementById('comboBadge');
        if (!badge) return;
        if (this.comboCount >= 2) {
            badge.textContent = this.comboCount >= 5 ? `🔥🔥 ${this.comboCount}x COMBO` : `🔥 ${this.comboCount}x COMBO`;
            badge.style.display = 'block';
            badge.className = 'combo-badge' + (this.comboCount >= 5 ? ' combo-hot' : '');
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
                this.updateHUD();
            }
        } catch (e) {
            this.log("SESSION SYNC ERROR", "#ff3e3e");
        }
    }

    renderDeckLoading() {
        const dc = document.getElementById('deckCards');
        if (!dc) return;
        dc.innerHTML = `
            <div class="mol-card loading"><div class="mol-loading-text">GENERATING...</div></div>
            <div class="mol-card loading"><div class="mol-loading-text">GENERATING...</div></div>
            <div class="mol-card loading"><div class="mol-loading-text">GENERATING...</div></div>
        `;
    }

    async fetchDeck() {
        if (!this.sessionId) return;
        try {
            const resp = await fetch(`/api/v3/game/session/${this.sessionId}/candidates`);
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

    renderFallbackDeck() {
        const smiles = window.GAME_STARTER_SMILES || '';
        this.currentDeck = [{ smiles, name: 'SEED-1', composite: 0.4, qed: 0.4, sas: 4, lipinski: true }];
        this.renderDeck(this.currentDeck);
    }

    renderDeck(candidates) {
        const dc = document.getElementById('deckCards');
        if (!dc) return;
        dc.innerHTML = '';
        candidates.forEach((c, i) => {
            const pct = Math.round(c.composite * 100);
            const barColor = pct >= 65 ? '#3fb950' : pct >= 50 ? '#f6ad55' : '#ff3e3e';
            const shortSmiles = c.smiles.length > 22 ? c.smiles.substring(0, 22) + '...' : c.smiles;
            const div = document.createElement('div');
            div.className = `mol-card${i === 0 ? ' selected' : ''}`;
            div.id = `card-${i}`;
            div.innerHTML = `
                <div class="mol-card-key">[${i + 1}]</div>
                <div class="mol-card-name">${c.name}</div>
                <div class="mol-card-smiles">${shortSmiles}</div>
                <div class="mol-card-power">
                    <div class="power-bar" style="width:${pct}%;background:${barColor};"></div>
                </div>
                <div class="mol-card-pct" style="color:${barColor}">${pct}%</div>
            `;
            div.addEventListener('click', () => this.selectCard(i));
            dc.appendChild(div);
        });
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

    setupEventListeners() {
        window.addEventListener('resize', () => {
            if (!this.container) return;
            this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        });

        window.addEventListener('keydown', e => {
            this.keys[e.code] = true;
            if (e.code === 'Space' && !e.repeat) {
                e.preventDefault();
                this.onSpacebarFire();
            }
            if (e.code === 'Digit1') this.selectCard(0);
            if (e.code === 'Digit2') this.selectCard(1);
            if (e.code === 'Digit3') this.selectCard(2);
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
    }

    onSpacebarFire() {
        if (this.isGameOver || this.attackLocked || !this.gameStarted || !this.fireReady) return;
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
        if (this.isAiming && !this.isGameOver && !this.attackLocked && this.gameStarted) {
            this.launchAttack();
        }
        this.isAiming = false;
        document.getElementById('crosshair-ui')?.classList.remove('aiming');
    }

    async launchAttack() {
        if (!this.selectedSmiles || this.attackLocked || this.isGameOver) return;
        this.attackLocked = true;

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
            this.fetchDeck();
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

        if (composite >= 0.55) {
            this.comboCount++;
        } else {
            this.comboCount = 0;
        }
        this.updateComboDisplay();

        const comboDmgBonus = this.comboCount >= 3 ? 1.25 : 1;
        this.createExplosion(this.monster.position.clone(), this.bossProfile.color || 0xff3e3e, 2 * comboDmgBonus);
        this.showFloatingDamage(damage * comboDmgBonus, isNewBest);
        this.updateHUD();
        this.showScienceCard(data);
        this.setBossWounded();

        if (data.won) { this.onVictory(data); return; }
        if (data.lost) {
            this.isGameOver = true;
            document.getElementById('screen-game-over').style.display = 'flex';
            return;
        }

        this.attackLocked = false;
        setTimeout(() => this.fetchDeck(), 500);
    }

    showFloatingDamage(damage, isNewBest) {
        const div = document.createElement('div');
        div.className = 'float-dmg' + (isNewBest ? ' float-dmg-best' : damage > 0 ? ' float-dmg-hit' : ' float-dmg-miss');
        div.textContent = damage > 0 ? `-${damage.toFixed(1)} HP` : 'NO IMPROVEMENT';
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
        const isNewBest = data.is_new_best;

        document.getElementById('scMolName').textContent = molCodename(data.best_smiles || '');
        document.getElementById('scPowerVal').textContent = `${Math.round(composite * 100)}%`;
        document.getElementById('scPowerVal').style.color = composite >= 0.65 ? '#3fb950' : composite >= 0.5 ? '#f6ad55' : '#ff3e3e';
        document.getElementById('scQED').textContent = toStars(qed, 1);
        document.getElementById('scSAS').textContent = sasToStars(sas);
        document.getElementById('scLipinski').textContent = lipinski ? '✅ Yes' : '❌ No';
        document.getElementById('scMsg').textContent = getAttackMsg(composite, window.GAME_BOSS_NAME || 'the pathogen', isNewBest);
        const nb = document.getElementById('scNewBest');
        if (nb) nb.style.display = isNewBest ? 'block' : 'none';

        const card = document.getElementById('scienceCard');
        if (card) card.classList.add('visible');

        if (this.scienceCardTimer) clearTimeout(this.scienceCardTimer);
        this.scienceCardTimer = setTimeout(() => this.hideScienceCard(), 7000);

        this.playTTS(getAttackMsg(composite, window.GAME_BOSS_NAME || 'the boss', isNewBest).replace(/🏆/g,''));
    }

    hideScienceCard() {
        const card = document.getElementById('scienceCard');
        if (card) card.classList.remove('visible');
        if (this.scienceCardTimer) { clearTimeout(this.scienceCardTimer); this.scienceCardTimer = null; }
    }

    setBossWounded() {
        const hpPct = this.bossHP / (window.GAME_INITIAL_HP || 100);
        if (hpPct < 0.5 && this.bossProfile.rotY) {
            this.bossProfile._rotYBoost = this.bossProfile.rotY * 0.5;
        }
    }

    updateWinMarker() {
        const marker = document.getElementById('win-threshold-marker');
        if (marker) marker.style.left = `${this.winThreshold * 100}%`;
    }

    updateHUD() {
        const initHP = window.GAME_INITIAL_HP || 100;
        document.getElementById('enemy-hp-fill').style.width = `${Math.max(0, this.bossHP / initHP * 100)}%`;
        document.getElementById('enemy-hp-text').innerText = `${this.bossHP.toFixed(1)} HP`;
        document.getElementById('player-hp-fill').style.width = `${this.playerHP / 10}%`;
        document.getElementById('player-hp-text').innerText = `${this.playerHP} / 1000`;
        const bsPct = Math.min(100, this.bestScore / Math.max(this.winThreshold, 0.01) * 100);
        document.getElementById('best-score-fill').style.width = `${bsPct}%`;
        document.getElementById('best-score-text').textContent = `${Math.round(this.bestScore * 100)}%`;
        const ac = document.getElementById('attack-counter');
        if (ac) ac.textContent = `ATTACKS: ${this.attackCount}`;
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
            new Audio(URL.createObjectURL(blob)).play().catch(() => {});
        } catch (e) {}
    }

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
        this.playerHP = Math.max(0, this.playerHP - val);
        const vd = document.getElementById('vfx-damage');
        if (vd) { vd.style.opacity = 0.5; setTimeout(() => vd.style.opacity = 0, 150); }
        this.updateHUD();
        if (this.playerHP <= 0 && !this.isGameOver) {
            this.isGameOver = true;
            document.getElementById('screen-game-over').style.display = 'flex';
        }
    }

    async onVictory(result) {
        this.isGameOver = true;
        this.wonMolecule = { smiles: result.best_smiles, tanimoto: result.best_props?.tanimoto || 0 };
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

    animateBoss(t) {
        if (!this.monster) return;
        const p = this.bossProfile;
        this.monster.rotation.y += (p.rotY || 0.015) + (p._rotYBoost || 0);
        this.monster.rotation.x += (p.rotX || 0.005);

        // Random wandering movement during battle
        if (this.gameStarted) {
            if (t * 1000 > this.bossMoveTimer) {
                this.bossMoveTimer = t * 1000 + 1800 + Math.random() * 2500;
                this.bossTargetX = (Math.random() - 0.5) * 28;
                this.bossTargetY = 2 + Math.random() * 10;
            }
            this.monster.position.x += (this.bossTargetX - this.monster.position.x) * 0.018;
            this.monster.position.y += (this.bossTargetY - this.monster.position.y) * 0.018;
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
        const hpPct = this.bossHP / (window.GAME_INITIAL_HP || 100);
        if (hpPct < 0.25) this.monster.visible = Math.random() > 0.08;
    }

    animate() {
        if (this.isGameOver) { this.renderer.render(this.scene, this.camera); return; }
        requestAnimationFrame(() => this.animate());

        const now = Date.now();
        const dt = Math.min((now - this.lastFrameTime) / 1000, 0.05);
        this.lastFrameTime = now;
        const t = now / 1000;

        // Arrow key ship movement
        if (this.gameStarted && this.playerShip) {
            const shipSpeed = 22;
            if (this.keys['ArrowLeft'])  this.playerShipX = Math.max(-22, this.playerShipX - shipSpeed * dt);
            if (this.keys['ArrowRight']) this.playerShipX = Math.min(22,  this.playerShipX + shipSpeed * dt);
            this.playerShip.position.x += (this.playerShipX - this.playerShip.position.x) * 0.18;
            this.playerShip.rotation.z = -(this.playerShipX - this.playerShip.position.x) * 0.12;
            // Thruster pulse
            if (this.playerShip.userData.thruster) {
                const intensity = 0.4 + Math.sin(t * 12) * 0.3;
                this.playerShip.userData.thruster.material.emissiveIntensity = intensity;
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
                p.mesh.position.x = this.monster.position.x + Math.cos(t * 4 + i) * 2;
                p.mesh.position.y = this.monster.position.y + Math.sin(t * 4 + i) * 2;
                if (p.apiSettled) {
                    this.applyAttackResult(p.apiResult, p);
                } else if (Date.now() - p.hitTime > 12000) {
                    this.applyAttackResult(null, p);
                }
                continue;
            }

            // Update target to track moving boss
            if (this.monster) p.targetPos.copy(this.monster.position);

            p.t += 0.01 * p.speed;
            const nextPos = new THREE.Vector3().lerpVectors(p.startPos, p.targetPos, Math.min(p.t, 1));
            if (p.isParabolic) nextPos.y += Math.sin(Math.min(p.t, 1) * Math.PI) * 12;
            p.mesh.lookAt(nextPos); p.mesh.position.copy(nextPos);

            if (p.mesh.position.distanceTo(this.monster.position) < 9) {
                p.parked = true; p.hitTime = Date.now();
                this.showAnalyzing(p.molName);
                continue;
            }

            let hitSomething = false;

            // Check safe object collision (friendly fire)
            for (let si = this.safeObjects.length - 1; si >= 0; si--) {
                const safe = this.safeObjects[si];
                if (p.mesh.position.distanceTo(safe.position) < 3.5) {
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

            // Check enemy obstacle collision
            for (let oi = this.obstacles.length - 1; oi >= 0; oi--) {
                const obs = this.obstacles[oi];
                if (p.mesh.position.distanceTo(obs.position) < (obs.isLarge ? 7 : 5)) {
                    obs.health--;
                    if (obs.health <= 0) { this.createExplosion(obs.position, 0x00f2ff, 1.5); this.scene.remove(obs); this.obstacles.splice(oi, 1); }
                    this.scene.remove(p.mesh); this.projectiles.splice(i, 1);
                    hitSomething = true; break;
                }
            }
            if (!hitSomething && p.t > 1.8) { this.scene.remove(p.mesh); this.projectiles.splice(i, 1); }
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

document.addEventListener('DOMContentLoaded', () => { new PathoHunt3D(); });
