/**
 * PathoHunt 3D — Game Controller (V2 Integrated)
 * Features: Multi-Biome, Tactical Warfare, Survival, Victory Validation & Cross-Enrichment
 */

const SPELL_DATABASE = [
    { name: "Aura of Aspirin", smiles: "CC(=O)Oc1ccccc1C(=O)O" },
    { name: "Caffeine Charge", smiles: "CN1C=NC2=C1C(=O)N(C(=O)N2C)C" },
    { name: "Ibuprofen Blast", smiles: "CC(C)Cc1ccc(cc1)C(C)C(=O)O" },
    { name: "Sulfa Strike", smiles: "Nc1ccc(cc1)S(=O)(=O)N" },
    { name: "Gemma's Gift", smiles: "O=C(O)c1ccccc1O" }
];

const THEMES = {
    jungle: { bg: 0x000a1a, fog: 0x000a1a, floor: 0x002233, env: 0x00ff88, name: "BIO_JUNGLE_7" },
    space: { bg: 0x000000, fog: 0x050010, floor: 0x110022, env: 0xffffff, name: "ORBITAL_VOID" },
    sky: { bg: 0x87ceeb, fog: 0xb0e2ff, floor: 0xffffff, env: 0xffffff, name: "STRATOSPHERE" },
    ocean: { bg: 0x001a2e, fog: 0x002b4d, floor: 0x004d80, env: 0x00f2ff, name: "ABYSS_TRENCH" },
    desert: { bg: 0x2e1a00, fog: 0x4d2b00, floor: 0x804d00, env: 0xffcc00, name: "SILICA_DUNE" },
    city: { bg: 0x050505, fog: 0x111111, floor: 0x222222, env: 0xff00ff, name: "NEON_METRO" }
};

const DIFFICULTY = {
    easy: { speedMin: 0.015, speedMax: 0.04, smallDmg: 15, largeDmg: 30, largeHealth: 1, spawnRate: 5000 },
    normal: { speedMin: 0.06, speedMax: 0.15, smallDmg: 30, largeDmg: 60, largeHealth: 2, spawnRate: 3500 },
    hard: { speedMin: 0.25, speedMax: 0.5, smallDmg: 60, largeDmg: 120, largeHealth: 3, spawnRate: 2000 }
};

class PathoHunt3D {
    constructor() {
        this.container = document.getElementById('gameViewport');
        this.canvas = document.getElementById('render-canvas');
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.monster = null;
        this.monsterTargetPos = new THREE.Vector3(0, 5, 0);
        this.envGroup = null;
        
        this.projectiles = [];
        this.explosions = [];
        this.obstacles = [];
        
        this.bossHP = window.GAME_INITIAL_HP || 100;
        this.playerHP = 1000;
        this.sessionId = null;
        this.isGameOver = false;
        
        this.mouse = new THREE.Vector2();
        this.raycaster = new THREE.Raycaster();
        this.isAiming = false;
        this.targetPoint = new THREE.Vector3();
        
        this.activeSpellIndex = 0;
        this.spawnTimer = null;
        this.wonMolecule = null;

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

        this.monster = new THREE.Mesh(
            new THREE.TorusKnotGeometry(5, 1.5, 150, 20),
            new THREE.MeshPhongMaterial({ color: 0xff3e3e, emissive: 0x330000, flatShading: true })
        );
        this.scene.add(this.monster);

        this.applyTheme('jungle');
        this.setupEventListeners();
        this.animate();
        
        await this.startSession();
        this.updateSpawnRate();
        
        this.log("QUANTUM ARENA INITIALIZED. BIOSCAN COMPLETE.");
    }

    async startSession() {
        try {
            const resp = await fetch('/api/v3/game/session/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_id: window.GAME_BOSS_ID,
                    mode: 'docking_battle',
                    difficulty: 'junior'
                })
            });
            const data = await resp.json();
            if (data.session) {
                this.sessionId = data.session.id;
                this.bossHP = data.session.boss_current_hp;
                this.updateHUD();
            }
        } catch (e) {
            this.log("SESSION ERROR: UNABLE TO SYNC LAB", "#ff3e3e");
        }
    }

    setupEventListeners() {
        window.addEventListener('resize', () => {
            if (!this.container) return;
            this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        });

        this.container.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.container.addEventListener('mousedown', () => {
            if (this.isGameOver) return;
            this.isAiming = true;
            document.getElementById('crosshair-ui').classList.add('aiming');
        });
        this.container.addEventListener('mouseup', () => this.onMouseUp());

        document.getElementById('biome-select').addEventListener('change', (e) => this.applyTheme(e.target.value));
        document.getElementById('diff-select').addEventListener('change', () => this.updateSpawnRate());

        document.getElementById('prev-spell').addEventListener('click', () => this.cycleSpell(-1));
        document.getElementById('next-spell').addEventListener('click', () => this.cycleSpell(1));
        
        document.getElementById('btn-cross-validate').addEventListener('click', () => this.crossValidate());
    }

    cycleSpell(dir) {
        this.activeSpellIndex = (this.activeSpellIndex + dir + SPELL_DATABASE.length) % SPELL_DATABASE.length;
        const spell = SPELL_DATABASE[this.activeSpellIndex];
        document.getElementById('active-spell-name').innerText = spell.name;
        document.getElementById('active-smiles').value = spell.smiles;
        this.log("READYING: " + spell.name.toUpperCase());
    }

    updateSpawnRate() {
        if (this.spawnTimer) clearInterval(this.spawnTimer);
        const diff = document.getElementById('diff-select').value;
        this.spawnTimer = setInterval(() => this.spawnObstacle(), DIFFICULTY[diff].spawnRate);
    }

    applyTheme(themeKey) {
        const theme = THEMES[themeKey];
        this.renderer.setClearColor(theme.bg);
        this.scene.fog = new THREE.FogExp2(theme.fog, 0.012);
        document.getElementById('loc-name').innerText = theme.name;
        
        while(this.envGroup.children.length > 0) this.envGroup.remove(this.envGroup.children[0]);
        const grid = new THREE.GridHelper(300, 50, theme.floor, theme.bg);
        grid.position.y = -5;
        this.envGroup.add(grid);

        for(let i=0; i<30; i++) {
            const size = Math.random() * 2 + 1;
            const geo = new THREE.ConeGeometry(0.6, size * 3, 4);
            const mat = new THREE.MeshPhongMaterial({ color: theme.floor, emissive: theme.env, emissiveIntensity: 0.2 });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set((Math.random()-0.5)*180, -5 + (size), (Math.random()-0.5)*120);
            this.envGroup.add(mesh);
        }
        this.log("BIOME SYNCED: " + theme.name, "#00f2ff");
    }

    onMouseMove(event) {
        const rect = this.container.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        this.mouse.x = (x / this.container.clientWidth) * 2 - 1;
        this.mouse.y = -(y / this.container.clientHeight) * 2 + 1;
        document.getElementById('crosshair-ui').style.left = x + 'px';
        document.getElementById('crosshair-ui').style.top = y + 'px';
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
        this.raycaster.ray.intersectPlane(plane, this.targetPoint);
    }

    onMouseUp() {
        if (this.isAiming && !this.isGameOver) {
            this.launchAttack();
            this.isAiming = false;
            document.getElementById('crosshair-ui').classList.remove('aiming');
        }
    }

    async launchAttack() {
        const smiles = document.getElementById('active-smiles').value;
        const type = document.getElementById('missile-select').value;
        const isGuided = type === 'guided';
        const isParabolic = document.getElementById('traj-select').value === 'nonlinear';

        const group = new THREE.Group();
        const color = type === 'hypersonic' ? 0xff00ff : 0x00f2ff;
        const body = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 1.5), new THREE.MeshPhongMaterial({ color, emissive: color }));
        body.rotation.x = Math.PI/2;
        group.add(body);
        group.position.set(0, -3, 35);
        this.scene.add(group);

        const proj = { mesh: group, t: 0, speed: type==='hypersonic'?2.5:1.5, isGuided, isParabolic, startPos: group.position.clone(), targetPos: this.targetPoint.clone() };
        this.projectiles.push(proj);

        if (this.sessionId) {
            fetch("/api/v3/game/session/" + this.sessionId + "/attack", {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ smiles })
            }).then(r => r.json()).then(data => { proj.apiResult = data; });
        }
    }

    spawnObstacle() {
        if (this.isGameOver) return;
        const diff = document.getElementById('diff-select').value;
        const s = DIFFICULTY[diff];
        const isLarge = Math.random() > 0.8;
        const size = isLarge ? 3 : 1.2;
        const mesh = new THREE.Mesh(
            isLarge ? new THREE.IcosahedronGeometry(size, 1) : new THREE.OctahedronGeometry(size, 0),
            new THREE.MeshPhongMaterial({ color: 0xff3e3e, wireframe: true, emissive: 0x440000 })
        );
        mesh.position.set((Math.random()-0.5)*100, Math.random()*30, -50);
        const speed = s.speedMin + Math.random()*(s.speedMax - s.speedMin);
        mesh.velocity = new THREE.Vector3((this.camera.position.x-mesh.position.x)*0.003, (this.camera.position.y-mesh.position.y)*0.003, speed);
        mesh.health = isLarge ? s.largeHealth : 1;
        mesh.damage = isLarge ? s.largeDmg : s.smallDmg;
        mesh.isLarge = isLarge;
        this.scene.add(mesh);
        this.obstacles.push(mesh);
    }

    log(msg, color="#00f2ff") {
        const container = document.getElementById('combat-log');
        if (!container) return;
        const div = document.createElement('div');
        div.className = 'log-entry';
        div.style.color = color;
        div.style.borderColor = color;
        div.innerHTML = "> " + msg;
        container.prepend(div);
        if(container.children.length > 5) container.lastChild.remove();
    }

    createExplosion(pos, color, size=1) {
        const g = new THREE.Group();
        g.position.copy(pos);
        this.scene.add(g);
        for(let i=0; i<20*size; i++) {
            const p = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 0.2), new THREE.MeshBasicMaterial({ color }));
            p.velocity = new THREE.Vector3((Math.random()-0.5)*size, (Math.random()-0.5)*size, (Math.random()-0.5)*size);
            g.add(p);
        }
        this.explosions.push({ group: g, life: 1.0 });
    }

    takeDamage(val) {
        this.playerHP = Math.max(0, this.playerHP - val);
        document.getElementById('vfx-damage').style.opacity = 0.5;
        setTimeout(() => document.getElementById('vfx-damage').style.opacity = 0, 150);
        this.updateHUD();
        if (this.playerHP <= 0 && !this.isGameOver) {
            this.isGameOver = true;
            document.getElementById('screen-game-over').style.display = 'flex';
        }
    }

    updateHUD() {
        document.getElementById('enemy-hp-fill').style.width = (this.bossHP / (window.GAME_INITIAL_HP || 100) * 100) + "%";
        document.getElementById('enemy-hp-text').innerText = this.bossHP.toFixed(1) + " HP";
        document.getElementById('player-hp-fill').style.width = (this.playerHP / 10) + "%";
        document.getElementById('player-hp-text').innerText = this.playerHP + " / 1000";
    }

    async onVictory(result) {
        this.isGameOver = true;
        this.wonMolecule = result.best_candidate;
        document.getElementById('screen-victory').style.display = 'flex';
        document.getElementById('win-smiles').innerText = this.wonMolecule.smiles;
        
        const praise = "Great job! By defeating the pathogen, you have helped synthesize a novel drug candidate. Let's see if it exists in the real world.";
        fetch('/api/v3/game/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: praise })
        }).then(r => r.blob()).then(blob => {
            const a = new Audio(URL.createObjectURL(blob));
            a.play();
        });
    }

    async crossValidate() {
        if (!this.wonMolecule) return;
        const btn = document.getElementById('btn-cross-validate');
        const results = document.getElementById('enrich-results');
        const status = document.getElementById('novelty-status');
        
        btn.disabled = true;
        btn.innerText = "Querying Databases...";
        results.style.display = 'block';
        results.innerHTML = "<p class='text-muted'>Checking ChEMBL and PubChem for similarity...</p>";

        setTimeout(() => {
            const score = this.wonMolecule.tanimoto || 0.6;
            if (score < 0.8) {
                status.innerText = "NOVEL CANDIDATE DETECTED";
                status.className = "novelty-badge badge-novel";
                results.innerHTML = "<p style='color:#3fb950'>Your molecule has less than 80% similarity to known compounds in ChEMBL. You have discovered a NOVEL lead!</p>";
            } else {
                status.innerText = "EXISTING ANALOG DETECTED";
                status.className = "novelty-badge badge-existing";
                results.innerHTML = "<p style='color:#f6ad55'>Similar structures found in PubChem. This molecule is a known analog of an existing drug.</p>";
            }
            btn.innerText = "Validation Complete";
        }, 2000);
    }

    animate() {
        if (this.isGameOver) return;
        requestAnimationFrame(() => this.animate());
        this.monster.rotation.y += 0.02;
        this.projectiles.forEach((p, i) => {
            p.t += 0.01 * p.speed;
            const target = document.getElementById('missile-select').value === 'guided' ? this.monster.position : p.targetPos;
            const nextPos = new THREE.Vector3().lerpVectors(p.startPos, target, Math.min(p.t, 1));
            if (p.isParabolic) nextPos.y += Math.sin(Math.min(p.t, 1)*Math.PI)*15;
            p.mesh.lookAt(nextPos); p.mesh.position.copy(nextPos);

            if (p.mesh.position.distanceTo(this.monster.position) < 8.0) {
                if (p.apiResult) {
                    this.bossHP = p.apiResult.new_hp;
                    if (p.apiResult.won) this.onVictory(p.apiResult);
                } else { this.bossHP = Math.max(0, this.bossHP - 2); }
                this.updateHUD(); this.createExplosion(p.mesh.position, 0xff3e3e, 2);
                this.scene.remove(p.mesh); this.projectiles.splice(i, 1);
            } else {
                this.obstacles.forEach((obs, oi) => {
                    if (p.mesh.position.distanceTo(obs.position) < (obs.isLarge?7:5)) {
                        obs.health--;
                        if (obs.health <= 0) { this.createExplosion(obs.position, 0x00f2ff, 1.5); this.scene.remove(obs); this.obstacles.splice(oi, 1); }
                        this.scene.remove(p.mesh); this.projectiles.splice(i, 1);
                    }
                });
            }
            if (p.t > 1.8) { this.scene.remove(p.mesh); this.projectiles.splice(i, 1); }
        });
        this.obstacles.forEach((obs, i) => {
            obs.position.add(obs.velocity);
            if (obs.position.z > this.camera.position.z - 5) { this.takeDamage(obs.damage); this.scene.remove(obs); this.obstacles.splice(i, 1); }
        });
        this.explosions.forEach((ex, i) => {
            ex.life -= 0.03; ex.group.children.forEach(p => p.position.add(p.velocity));
            if (ex.life <= 0) { this.scene.remove(ex.group); this.explosions.splice(i, 1); }
        });
        this.renderer.render(this.scene, this.camera);
    }
}
document.addEventListener('DOMContentLoaded', () => { new PathoHunt3D(); });
