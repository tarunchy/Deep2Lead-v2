/* PathoHunt battle screen logic */
(function () {
  const BOSS = window.BOSS_DATA || {};

  let sessionId = null;
  let currentHp = BOSS.boss_initial_hp || 100;
  let totalDamage = 0;
  let attackCount = 0;
  let currentMode = 'quick_battle';
  let currentDiff = 'junior';
  let viewer3d = null;

  const DIFF_HINTS = {
    junior: 'Seed SMILES provided. Unlimited attempts. Best for beginners.',
    fellow: 'Partial seed hint. 10 attempt limit. Intermediate challenge.',
    pi: 'No seed hint. 5 attempts. Real drug-discovery difficulty.',
    nobel: 'No hints. 3 attempt rounds. Expert — AI Army recommended.',
  };

  /* ── Mode & difficulty selectors ── */
  window.selectMode = function (mode, btn) {
    currentMode = mode;
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  };

  window.selectDiff = function (diff, btn) {
    currentDiff = diff;
    document.querySelectorAll('.diff-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const hint = document.getElementById('diffHint');
    if (hint) hint.textContent = DIFF_HINTS[diff] || '';
  };

  /* ── Start battle ── */
  window.startBattle = async function () {
    const btn = document.getElementById('startBattleBtn');
    btn.disabled = true;
    btn.textContent = 'Starting…';

    try {
      const res = await fetch('/api/v3/game/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_id: BOSS.target_id,
          mode: currentMode,
          difficulty: currentDiff,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to start session');

      sessionId = data.session.id;
      currentHp = data.session.boss_current_hp;

      // Switch to arena view
      document.getElementById('sessionSetup').style.display = 'none';
      document.getElementById('battleArena').style.display = 'block';

      // Init HP bar
      setHp(currentHp, true);

      // Adjust seed SMILES visibility based on difficulty
      const smilesInput = document.getElementById('smilesInput');
      const seedHint = document.getElementById('seedHint');
      if (currentDiff === 'junior') {
        smilesInput.value = BOSS.known_drug_smiles || '';
        seedHint.textContent = '(pre-filled with reference drug)';
      } else if (currentDiff === 'fellow') {
        smilesInput.value = (BOSS.known_drug_smiles || '').slice(0, 20) + '…';
        seedHint.textContent = '(fragment hint only)';
      } else {
        smilesInput.value = '';
        seedHint.textContent = '(no hint — you must enter a SMILES)';
      }

      addLog('⚔️ Battle started! Defeat ' + (BOSS.game_name || 'the boss') + '!', 'normal');

      // Load 3D structure
      load3DStructure(BOSS.pdb_id);

    } catch (e) {
      btn.disabled = false;
      btn.textContent = '⚔️ Start Battle!';
      showAlert('Could not start battle: ' + e.message);
    }
  };

  /* ── Launch attack ── */
  window.launchAttack = async function () {
    if (!sessionId) return;
    const smiles = document.getElementById('smilesInput').value.trim();
    if (!smiles) { showAlert('Please enter a seed SMILES string.'); return; }

    const attackBtn = document.getElementById('attackBtn');
    const loading = document.getElementById('attackLoading');
    attackBtn.disabled = true;
    loading.classList.add('visible');
    document.getElementById('loadingMsg').textContent = 'Generating molecules with Gemma4…';

    try {
      const nMol = parseInt(document.getElementById('nMolecules').value) || 5;
      const noise = parseFloat(document.getElementById('noiseSel').value) || 0.35;

      const res = await fetch('/api/v3/game/session/' + sessionId + '/attack', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ smiles, n_molecules: nMol, noise }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Attack failed');

      attackCount++;
      const { damage, new_hp, best_smiles, best_props, won, lost, is_new_best } = data;

      // Update HP
      currentHp = new_hp;
      totalDamage += damage;
      setHp(new_hp);

      // Update stats
      document.getElementById('statAttacks').textContent = data.session.attacks_count;
      document.getElementById('statBest').textContent =
        (data.session.best_score * 100).toFixed(1) + '%';
      document.getElementById('statDamage').textContent = totalDamage.toFixed(1);
      document.getElementById('statHp').textContent = new_hp.toFixed(1) + '%';

      // Battle log entry
      if (damage > 0) {
        addLog('⚔️ Attack #' + attackCount + ': ' + damage.toFixed(1) + ' damage dealt!', 'damage');
        spawnDamagePop('-' + damage.toFixed(0));
        showXpPop('+XP');
      } else {
        addLog('💨 Attack #' + attackCount + ': No improvement — no damage.', 'miss');
      }

      if (is_new_best) {
        addLog('✨ New best score: ' + (best_props.composite_score * 100).toFixed(1) + '%', 'normal');
      }

      // Show result card
      showResultCard(best_smiles, best_props, damage);

      if (won) {
        setTimeout(() => showVictory(data.session, best_props), 800);
      } else if (lost) {
        setTimeout(() => showDefeat(data.session), 800);
      }

    } catch (e) {
      addLog('❌ Error: ' + e.message, 'miss');
      if (e.message.includes('AI generation failed') || e.message.includes('503')) {
        document.getElementById('loadingMsg').textContent = 'AI unreachable — check DGX server';
      }
    } finally {
      attackBtn.disabled = false;
      loading.classList.remove('visible');
    }
  };

  /* ── Abandon ── */
  window.abandonBattle = async function () {
    if (!sessionId) { window.location.href = '/game'; return; }
    if (!confirm('Abandon this battle? Your progress will be lost.')) return;
    await fetch('/api/v3/game/session/' + sessionId + '/abandon', { method: 'POST' });
    window.location.href = '/game';
  };

  /* ── HP bar ── */
  function setHp(hp, instant) {
    const fill = document.getElementById('hpFill');
    const label = document.getElementById('bossHpLabel');
    const pct = Math.max(0, Math.min(100, hp));

    if (instant) fill.style.transition = 'none';
    else fill.style.transition = 'width 0.7s cubic-bezier(.4,0,.2,1)';

    fill.style.width = pct + '%';
    fill.textContent = 'Simulation HP: ' + pct.toFixed(1) + '%';

    if (pct <= 30) fill.classList.add('low');
    else fill.classList.remove('low');

    if (label) label.textContent = 'Simulation HP: ' + pct.toFixed(1) + '%';
  }

  /* ── Battle log ── */
  function addLog(msg, type) {
    const log = document.getElementById('battleLog');
    const entry = document.createElement('div');
    entry.className = 'log-entry log-' + (type || 'normal');
    entry.textContent = msg;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
  }

  /* ── Result card ── */
  function showResultCard(smiles, props, damage) {
    const card = document.getElementById('resultCard');
    card.classList.add('visible');
    document.getElementById('resultSmiles').textContent = smiles || '—';

    const metrics = [
      { label: 'Score', value: props.composite_score != null ? (props.composite_score * 100).toFixed(1) + '%' : '—' },
      { label: 'QED', value: props.qed != null ? props.qed.toFixed(3) : '—' },
      { label: 'SAS', value: props.sas != null ? props.sas.toFixed(2) : '—' },
      { label: 'MW', value: props.mw != null ? props.mw.toFixed(0) + ' Da' : '—' },
      { label: 'Lipinski', value: props.lipinski_pass ? '✅ Pass' : '❌ Fail' },
      { label: 'Damage', value: damage != null ? damage.toFixed(1) : '0' },
    ];

    const container = document.getElementById('resultMetrics');
    container.innerHTML = metrics.map(m =>
      '<div class="metric-chip">' + m.label + ': <span>' + m.value + '</span></div>'
    ).join('');
  }

  /* ── Damage pop animation ── */
  function spawnDamagePop(text) {
    const el = document.createElement('div');
    el.className = 'damage-pop hit';
    el.textContent = text;
    const hpTrack = document.querySelector('.hp-track');
    const rect = hpTrack ? hpTrack.getBoundingClientRect() : { top: 200, left: 200 };
    el.style.top = (rect.top - 30 + window.scrollY) + 'px';
    el.style.left = (rect.left + 20) + 'px';
    document.body.appendChild(el);

    let y = 0;
    let op = 1;
    const anim = setInterval(() => {
      y -= 2;
      op -= 0.035;
      el.style.transform = 'translateY(' + y + 'px)';
      el.style.opacity = op;
      if (op <= 0) { clearInterval(anim); el.remove(); }
    }, 20);
  }

  /* ── XP toast ── */
  function showXpPop(text) {
    const el = document.createElement('div');
    el.className = 'xp-pop';
    el.textContent = text;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2600);
  }

  /* ── Alert ── */
  function showAlert(msg) {
    const el = document.createElement('div');
    el.className = 'alert alert-danger';
    el.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;padding:10px 20px;border-radius:8px;';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }

  /* ── Victory / Defeat ── */
  function showVictory(session, props) {
    document.getElementById('victoryOverlay').style.display = 'flex';
    document.getElementById('victoryMsg').textContent =
      'You defeated ' + (BOSS.game_name || 'the boss') + ' with score ' +
      (session.best_score * 100).toFixed(1) + '%!';
    document.getElementById('victoryScience').textContent =
      ' Best composite score ' + (session.best_score * 100).toFixed(1) +
      '% — better than the known drug baseline (' +
      ((BOSS.known_drug_score || 0) * 100).toFixed(0) + '%). ' +
      'This is a computational simulation result only.';
  }

  function showDefeat(session) {
    document.getElementById('defeatOverlay').style.display = 'flex';
    document.getElementById('defeatMsg').textContent =
      'You used all your attempts. Best score was ' +
      (session.best_score * 100).toFixed(1) + '% — need ' +
      (BOSS.win_threshold_easy * 100).toFixed(0) + '% to win.';
  }

  /* ── 3D protein viewer ── */
  function load3DStructure(pdbId) {
    if (!pdbId || typeof $3Dmol === 'undefined') return;
    const placeholder = document.getElementById('viewerPlaceholder');

    try {
      viewer3d = $3Dmol.createViewer(
        document.getElementById('battle3dmol'),
        { backgroundColor: '#161b22' }
      );
      const url = 'https://files.rcsb.org/download/' + pdbId + '.pdb';
      $3Dmol.download('pdb:' + pdbId, viewer3d, {}, function () {
        viewer3d.setStyle({}, { cartoon: { color: 'spectrum' } });
        viewer3d.zoomTo();
        viewer3d.render();
        if (placeholder) placeholder.style.display = 'none';
      });
    } catch (e) {
      if (placeholder) placeholder.textContent = '3D viewer unavailable';
    }
  }

  // Initial HP set (from known drug baseline)
  setHp(BOSS.boss_initial_hp || 100, true);

})();
