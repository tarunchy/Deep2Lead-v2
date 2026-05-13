/* ── PathoHunt 3D — In-Game Guide System ─────────────────────── */

// Per-pathogen molecule hints shown in the "Build It" guide step
const PATHOGEN_HINTS = {
    covid19_mpro: {
        rings:  'Pyrimidine or Benzene',
        groups: 'Nitrile (–CN) or Amide bond',
        why:    'The COVID protease has a cysteine pocket that binds nitrile warheads — exactly how Paxlovid works.',
    },
    influenza_na: {
        rings:  'Benzene or Pyridine',
        groups: 'Carboxyl (–COOH) and Amine (–NH2)',
        why:    'Tamiflu (oseltamivir) blocks this enzyme using a carboxylic acid + amine — mimicking the natural substrate.',
    },
    hiv_protease: {
        rings:  'Piperidine or Morpholine',
        groups: 'Hydroxyl (–OH) in the center',
        why:    'HIV drugs like Ritonavir grip the enzyme with a central hydroxyl flanked by two ring systems.',
    },
    egfr_kinase: {
        rings:  'Pyrimidine + Benzene',
        groups: 'Amide bond',
        why:    'EGFR inhibitors like Gefitinib use a pyrimidine to outcompete the cell\'s own ATP molecule.',
    },
    braf_v600e: {
        rings:  'Indole + Pyrimidine',
        groups: 'Sulfonamide',
        why:    'Vemurafenib, the approved melanoma drug, uses a large indole-sulfonamide scaffold.',
    },
    sirt1: {
        rings:  'Benzene or Indole',
        groups: 'Amide bond or Hydroxyl',
        why:    'Sirtuin modulators often feature aromatic amide scaffolds that slot into the NAD+ binding pocket.',
    },
    cdk2: {
        rings:  'Pyrimidine or Imidazole',
        groups: 'Amine (–NH2) and Amide',
        why:    'CDK2 inhibitors mimic adenine using amino-pyrimidine scaffolds that compete with ATP.',
    },
};

const DEFAULT_HINT = {
    rings:  'Benzene or Pyridine',
    groups: 'Amine (–NH2) or Amide bond',
    why:    'Most drug candidates use an aromatic ring backbone with a polar functional group for protein binding.',
};

// ── Guide step definitions ───────────────────────────────────────

const GUIDE_STEPS = [
    {
        id:       'deck_loaded',
        trigger:  'deck_loaded',
        category: 'STEP 1 — FIRE',
        title:    'These Are Your Molecule Options',
        body:     `The AI generated <strong>drug candidates</strong> for you — each with a <strong>Drug Score %</strong>.<br><br>
                   The score measures how drug-like the molecule is based on real chemistry. <strong>Higher score = more damage dealt.</strong><br><br>
                   Press keys <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> to pick a card, then press <kbd>SPACE</kbd> or click the arena to fire!`,
        cta:      'Got it — I\'ll fire! →',
    },
    {
        id:       'after_first_attack',
        trigger:  'after_first_attack',
        category: 'STEP 2 — DESIGN',
        title:    'Now Try the Molecule Designer',
        body:     `The AI picked a molecule from its library. But <strong>you can design something more powerful.</strong><br><br>
                   Tap the <strong>flask button (🧪)</strong> near the molecule deck to open the <strong>Molecule Designer</strong>.<br><br>
                   Custom molecules — tuned to this specific pathogen — can score significantly higher than the defaults.`,
        cta:      'Show me how →',
        hint:     'Look for the 🧪 flask icon near the molecule deck',
    },
    {
        id:       'designer_opened',
        trigger:  'designer_opened',
        category: 'STEP 3 — BUILD',
        title:    'Two Ways to Create a Drug',
        body:     `You have two design modes:<br><br>
                   • <strong>Describe It</strong> — type what you want in plain English (e.g. "a benzene ring with an amine group")<br>
                   • <strong>Build It</strong> — click building blocks to assemble from scratch<br><br>
                   <strong>Build It</strong> is the easiest way to start — tap that tab now!`,
        cta:      'Switch to Build It →',
    },
    {
        id:       'build_tab_clicked',
        trigger:  'build_tab_clicked',
        category: 'STEP 4 — PATHOGEN INTEL',
        title:    'What to Build for This Pathogen',
        body:     '', // filled dynamically in showStep()
        cta:      'Got it — I\'ll build it! →',
    },
    {
        id:       'custom_mol_loaded',
        trigger:  'custom_mol_loaded',
        category: 'STEP 5 — ITERATE',
        title:    'Your Custom Drug is Loaded!',
        body:     `Your molecule has been scored against this pathogen's <strong>actual protein structure</strong>.<br><br>
                   The Drug Score reflects its drug-likeness, synthesizability, and fit to the protein binding pocket.<br><br>
                   <strong>Keep experimenting</strong> — try different building block combinations. Scientists who iterate most win fastest!`,
        cta:      'Keep going! →',
    },
];

// ── Guide System ─────────────────────────────────────────────────

const GuideSystem = (() => {
    let active    = false;
    let forced    = false; // true when wins < 2 (cannot be toggled off mid-game)
    let shown     = new Set();
    let currentId = null;

    function init() {
        const wins = window.WINS_COUNT ?? 99;
        forced = wins < 2;
        const userPref = localStorage.getItem('pathoguide');
        active = forced || userPref === 'on';

        if (!active) return;

        document.getElementById('guideCta')?.addEventListener('click', dismiss);

        // ESC only works for returning players who opted in (not forced)
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && currentId && !forced) dismiss();
        });
    }

    function trigger(eventName) {
        if (!active) return;
        const step = GUIDE_STEPS.find(s => s.trigger === eventName && !shown.has(s.id));
        if (!step) return;
        showStep(step);
    }

    function buildPathogenBody() {
        const tid  = window.GAME_BOSS_TARGET_ID || window.GAME_BOSS_ID || '';
        const hint = PATHOGEN_HINTS[tid] || DEFAULT_HINT;
        return `Pick building blocks to assemble your molecule:<br><br>
                <strong>1 — Ring System</strong> (backbone): try <strong style="color:#00f2ff">${hint.rings}</strong><br>
                <strong>2 — Functional Group</strong> (binding power): add <strong style="color:#00f2ff">${hint.groups}</strong><br><br>
                <span style="font-size:0.82rem;color:rgba(0,242,255,0.65)">
                    Why? ${hint.why}
                </span><br><br>
                Select at least 2 blocks, then click <strong>Assemble Molecule</strong>!`;
    }

    function showStep(step) {
        currentId = step.id;
        shown.add(step.id);

        const overlay = document.getElementById('guideOverlay');
        if (!overlay) return;

        const body = step.id === 'build_tab_clicked' ? buildPathogenBody() : step.body;

        document.getElementById('guideCat').textContent   = step.category;
        document.getElementById('guideTitle').textContent = step.title;
        document.getElementById('guideBody').innerHTML    = body;
        document.getElementById('guideCta').textContent   = step.cta;

        const hintEl = document.getElementById('guideHint');
        if (step.hint) {
            hintEl.textContent    = '↳ ' + step.hint;
            hintEl.style.display  = 'block';
        } else {
            hintEl.style.display  = 'none';
        }

        overlay.style.display = 'flex';
    }

    function dismiss() {
        const overlay   = document.getElementById('guideOverlay');
        if (overlay) overlay.style.display = 'none';
        const justDone  = currentId;
        currentId = null;

        // Side-effects on certain dismissals
        if (justDone === 'after_first_attack') {
            pulseDesignerBtn();
        } else if (justDone === 'designer_opened') {
            // Auto-switch to Build It tab
            document.querySelector('.mdes-tab[data-tab="build"]')?.click();
        }
    }

    function pulseDesignerBtn() {
        const btn = document.getElementById('btnDesignMol');
        if (!btn) return;
        btn.classList.add('guide-pulse');
        setTimeout(() => btn.classList.remove('guide-pulse'), 6000);
    }

    function isForced()  { return forced; }
    function isActive()  { return active; }

    function setActive(on) {
        if (forced) return; // can't toggle off during forced tutorial
        active = on;
        localStorage.setItem('pathoguide', on ? 'on' : 'off');
    }

    document.addEventListener('DOMContentLoaded', init);

    return { trigger, isActive, isForced, setActive };
})();
