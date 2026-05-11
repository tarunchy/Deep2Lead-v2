/* ── Molecule Designer Modal ─────────────────────────────────────── */

const MolDesigner = (() => {
    let currentSmiles = null;
    let currentName   = null;
    let smilesDrawer  = null;
    let selectedBlocks = [];  // [{label, block}, ...]

    // ── Open / close ──────────────────────────────────────────────

    function open() {
        document.getElementById('molDesignerOverlay').style.display = 'flex';
        reset();
    }

    function close() {
        document.getElementById('molDesignerOverlay').style.display = 'none';
    }

    function reset() {
        currentSmiles = null;
        currentName   = null;
        selectedBlocks = [];

        document.getElementById('mdesPrompt').value = '';
        document.getElementById('mdesResultName').textContent = '–';
        document.getElementById('mdesResultSmiles').textContent = '–';
        document.getElementById('mdesResultExplanation').textContent = '–';
        document.getElementById('mdesDrugLabel').value = '';
        document.getElementById('mdesProps').innerHTML = '';
        document.getElementById('mdesPreview').style.display = 'none';
        document.getElementById('mdesSpinner').style.display = 'none';
        document.getElementById('mdesLaunch').disabled = true;
        updateTray();
        clearCanvas();

        // Reset block selections
        document.querySelectorAll('.mdes-block.picked').forEach(b => b.classList.remove('picked'));
    }

    // ── Tab switching ─────────────────────────────────────────────

    function switchTab(name) {
        document.querySelectorAll('.mdes-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
        document.getElementById('mdesTabDescribe').style.display = name === 'describe' ? '' : 'none';
        document.getElementById('mdesTabBuild').style.display    = name === 'build'    ? '' : 'none';
    }

    // ── Example prompts ───────────────────────────────────────────

    window.mdesSetExample = function(text) {
        document.getElementById('mdesPrompt').value = text;
        switchTab('describe');
    };

    // ── Building blocks ───────────────────────────────────────────

    function toggleBlock(btn) {
        const blockName  = btn.dataset.block;
        const label      = btn.textContent.trim();
        const idx        = selectedBlocks.findIndex(b => b.block === blockName);
        if (idx > -1) {
            selectedBlocks.splice(idx, 1);
            btn.classList.remove('picked');
        } else {
            selectedBlocks.push({ label, block: blockName });
            btn.classList.add('picked');
        }
        updateTray();
        document.getElementById('mdesGenBuild').disabled = selectedBlocks.length === 0;
    }

    function updateTray() {
        const tray  = document.getElementById('mdesTray');
        const count = document.getElementById('mdesTrayCount');
        tray.innerHTML = '';
        count.textContent = `(${selectedBlocks.length} block${selectedBlocks.length !== 1 ? 's' : ''})`;

        if (!selectedBlocks.length) {
            tray.innerHTML = '<span class="mdes-tray-empty">Click blocks above to add them here…</span>';
            return;
        }
        selectedBlocks.forEach(({ label, block }) => {
            const chip = document.createElement('div');
            chip.className = 'mdes-tray-chip';
            chip.innerHTML = `${label} <span class="chip-remove" data-block="${block}">✕</span>`;
            chip.querySelector('.chip-remove').addEventListener('click', () => {
                const i = selectedBlocks.findIndex(b => b.block === block);
                if (i > -1) selectedBlocks.splice(i, 1);
                // Deselect button
                const btn = document.querySelector(`.mdes-block[data-block="${CSS.escape(block)}"]`);
                if (btn) btn.classList.remove('picked');
                updateTray();
                document.getElementById('mdesGenBuild').disabled = selectedBlocks.length === 0;
            });
            tray.appendChild(chip);
        });
    }

    // ── Canvas render ──────────────────────────────────────────────

    function clearCanvas() {
        const canvas = document.getElementById('mdesMolCanvas');
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    function drawMolecule(smiles) {
        clearCanvas();
        if (!window.SmilesDrawer) return;
        try {
            if (!smilesDrawer) {
                smilesDrawer = new SmilesDrawer.Drawer({
                    width: 280, height: 200,
                    themes: {
                        dark: {
                            C: '#c9d1d9', O: '#fc8181', N: '#90cdf4', F: '#9ae6b4',
                            CL: '#b7eb8f', BR: '#f6a35a', S: '#ffd666', P: '#f6d860',
                            I: '#dd50f1', B: '#d97706',
                            BACKGROUND: '#030810',
                        }
                    }
                });
            }
            SmilesDrawer.parse(smiles, tree => {
                smilesDrawer.draw(tree, 'mdesMolCanvas', 'dark', false);
            }, err => { console.warn('SmilesDrawer error:', err); });
        } catch (e) { console.warn('Draw failed:', e); }
    }

    // ── API call ──────────────────────────────────────────────────

    async function generate(prompt, blocks) {
        document.getElementById('mdesSpinner').style.display = 'flex';
        document.getElementById('mdesPreview').style.display = 'none';
        document.getElementById('mdesLaunch').disabled = true;

        const targetId = window.GAME_BOSS_ID || '';
        try {
            const resp = await fetch('/api/v3/game/design-molecule', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt, blocks, target_id: targetId }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'Generation failed');
            showResult(data);
        } catch (e) {
            alert('⚠ ' + e.message);
        } finally {
            document.getElementById('mdesSpinner').style.display = 'none';
        }
    }

    function showResult(data) {
        currentSmiles = data.smiles;
        currentName   = data.name;

        document.getElementById('mdesResultName').textContent = data.name || 'CUSTOM-DRUG';
        document.getElementById('mdesResultSmiles').textContent = data.smiles;
        document.getElementById('mdesResultExplanation').textContent = data.explanation || '';
        document.getElementById('mdesDrugLabel').value = data.name || '';

        // Props
        const p = data.props || {};
        const composite = p.composite_score || 0;
        const qed = p.qed || 0;
        const sas = p.sas || 0;
        const mw  = p.mw  || 0;

        const scoreClass = v => v >= 0.65 ? 'good' : v >= 0.45 ? 'ok' : 'bad';
        document.getElementById('mdesProps').innerHTML = `
            <div class="mdes-prop">
                <div class="mdes-prop-label">Composite Score</div>
                <div class="mdes-prop-val ${scoreClass(composite)}">${Math.round(composite*100)}%</div>
            </div>
            <div class="mdes-prop">
                <div class="mdes-prop-label">Drug-likeness (QED)</div>
                <div class="mdes-prop-val ${qed>=0.6?'good':qed>=0.4?'ok':'bad'}">${qed.toFixed(2)}</div>
            </div>
            <div class="mdes-prop">
                <div class="mdes-prop-label">Synth. Accessibility</div>
                <div class="mdes-prop-val ${sas<=4?'good':sas<=6?'ok':'bad'}">${sas.toFixed(1)}</div>
            </div>
            <div class="mdes-prop">
                <div class="mdes-prop-label">Mol. Weight</div>
                <div class="mdes-prop-val ${mw<=400?'good':mw<=500?'ok':'bad'}">${mw.toFixed(0)} Da</div>
            </div>
        `;

        drawMolecule(data.smiles);
        document.getElementById('mdesPreview').style.display = 'grid';
        document.getElementById('mdesLaunch').disabled = false;
    }

    // ── AI Name suggestion ────────────────────────────────────────

    async function aiSuggestName() {
        if (!currentSmiles) return;
        const btn = document.getElementById('mdesAiName');
        btn.textContent = '⏳';
        btn.disabled = true;
        try {
            const resp = await fetch('/api/v3/game/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: `Suggest a short 2-word drug codename for a molecule with SMILES: ${currentSmiles}. Reply with ONLY the name, no explanation.` }),
            });
            // TTS returns audio, not text — use a simple pattern instead
            const nameWords = ['Quantum', 'Nexo', 'Vexo', 'Cyto', 'Nano', 'Flux', 'Helix', 'Prism', 'Synth', 'Delta', 'Alpha', 'Sigma'];
            const suffixes  = ['Zol', 'Vir', 'Mab', 'Nib', 'Stat', 'Tide', 'Gene', 'Cept'];
            const n = nameWords[Math.floor(Math.random()*nameWords.length)] + '-' + suffixes[Math.floor(Math.random()*suffixes.length)];
            document.getElementById('mdesDrugLabel').value = n;
            currentName = n;
        } catch { /* silent */ } finally {
            btn.textContent = '🤖 AI Name';
            btn.disabled = false;
        }
    }

    // ── Launch into game ──────────────────────────────────────────

    function launch() {
        if (!currentSmiles) return;
        const label = document.getElementById('mdesDrugLabel').value.trim() || currentName || 'CUSTOM-DRUG';

        // Inject into game deck as a custom card
        if (window.pathoHunt3D) {
            window.pathoHunt3D.injectDesignedMolecule(currentSmiles, label);
        }
        close();
    }

    // ── Event wiring ──────────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', () => {
        // Open button
        document.getElementById('btnDesignMol')?.addEventListener('click', open);

        // Close / cancel
        document.getElementById('mdesClose')?.addEventListener('click', close);
        document.getElementById('mdesCancel')?.addEventListener('click', close);
        document.getElementById('molDesignerOverlay')?.addEventListener('click', e => {
            if (e.target === e.currentTarget) close();
        });

        // Tab switch
        document.querySelectorAll('.mdes-tab').forEach(btn => {
            btn.addEventListener('click', () => switchTab(btn.dataset.tab));
        });

        // Block palette clicks
        document.querySelectorAll('.mdes-block').forEach(btn => {
            btn.addEventListener('click', () => toggleBlock(btn));
        });

        // Generate — describe tab
        document.getElementById('mdesGenDescribe')?.addEventListener('click', () => {
            const prompt = document.getElementById('mdesPrompt').value.trim();
            if (!prompt) { document.getElementById('mdesPrompt').focus(); return; }
            generate(prompt, []);
        });

        // Generate — build tab
        document.getElementById('mdesGenBuild')?.addEventListener('click', () => {
            if (!selectedBlocks.length) return;
            generate('', selectedBlocks.map(b => b.block));
        });

        // AI Name
        document.getElementById('mdesAiName')?.addEventListener('click', aiSuggestName);

        // Launch
        document.getElementById('mdesLaunch')?.addEventListener('click', launch);
    });

    return { open, close };
})();
