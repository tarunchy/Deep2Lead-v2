/* PathoHunt Interactive Tutorial — step engine + Kokoro TTS */
(function () {
  /* ── Tutorial script ─────────────────────────────────────────────────── */
  const STEPS = [
    {
      title: "Welcome to PathoHunt!",
      category: "Introduction",
      visual: "bosses",
      text: "Welcome to PathoHunt! I'm Professor AI, your lab guide. This tutorial will show you how to fight pathogens using <strong>real computational chemistry</strong>. Each step takes about 20 seconds. You can navigate with the buttons below or use your keyboard arrows.",
      audio_text: "Welcome to PathoHunt! I'm Professor AI, your lab guide. This tutorial will show you how to fight pathogens using real computational chemistry. Each step takes about 20 seconds. You can navigate with the buttons below or use your keyboard arrows.",
    },
    {
      title: "What Are Pathogen Bosses?",
      category: "Core Concept",
      visual: "bosses",
      text: "Each level features a <strong>real disease-causing protein</strong>. The Flu Commander is Influenza Neuraminidase — the enzyme that helps flu viruses escape from cells. The Corona Cutter is the COVID-19 main protease. These are <em>real molecular targets that real scientists study</em>.",
      audio_text: "Each level features a real disease-causing protein. The Flu Commander is Influenza Neuraminidase — the enzyme that helps flu viruses escape from cells. The Corona Cutter is the COVID-19 main protease. These are real molecular targets that real scientists study.",
    },
    {
      title: "The Simulation Health Bar",
      category: "Game Mechanics",
      visual: "hpbar",
      text: "Every boss has a <strong>Simulation Health Bar</strong>. It already starts depleted — because the best known drug already weakens this target. Your mission: design a <em>better molecule</em> than the known drug and push that HP to zero. The bar is always labeled Simulation — it never represents real-world results.",
      audio_text: "Every boss has a Simulation Health Bar. It already starts depleted, because the best known drug already weakens this target. Your mission: design a better molecule than the known drug and push that health to zero.",
    },
    {
      title: "SMILES — Your Ammunition",
      category: "Chemistry Basics",
      visual: "smiles",
      text: "Your weapon is a <strong>SMILES string</strong> — a text code that describes a molecule's chemical structure. <em>C</em> is carbon, <em>N</em> is nitrogen, <em>O</em> is oxygen. Ring atoms are in brackets. Don't worry about memorizing this — on Junior difficulty, we give you the known drug as a starting seed!",
      audio_text: "Your weapon is a SMILES string — a text code that describes a molecule's chemical structure. C is carbon, N is nitrogen, O is oxygen. Ring atoms go in brackets. On Junior difficulty, we give you the known drug as a starting seed, so you don't need to write SMILES from scratch.",
    },
    {
      title: "Generating Molecules with AI",
      category: "AI Generation",
      visual: "ai_flow",
      text: "Click <strong>Generate & Attack with AI</strong>. The Gemma4 language model reads your seed SMILES and generates up to 10 variations — similar molecules with chemical tweaks. All candidates are scored automatically. Your <em>best-scoring molecule</em> is selected and used as your attack.",
      audio_text: "Click Generate and Attack with AI. The Gemma4 language model reads your seed SMILES and generates up to ten variations — similar molecules with chemical tweaks. All candidates are scored automatically. Your best-scoring molecule is selected and used as your attack.",
    },
    {
      title: "How Scoring Works",
      category: "Scoring",
      visual: "scoring",
      text: "Your molecule gets three scores. <strong>QED</strong> measures drug-likeness — does it look like a real drug? <strong>SAS</strong> measures synthetic accessibility — can a chemist actually make it? <strong>Tanimoto</strong> measures similarity to the seed. These combine into one <em>composite score</em> from 0 to 100 percent.",
      audio_text: "Your molecule gets three scores. QED measures drug-likeness — does it look like a real drug? SAS measures synthetic accessibility — can a chemist actually make it? Tanimoto measures similarity to the seed. These combine into one composite score from zero to one hundred percent.",
    },
    {
      title: "Dealing Damage",
      category: "Game Mechanics",
      visual: "damage",
      text: "If your composite score is <strong>better than your previous best</strong> — you deal damage! The bigger the improvement, the more HP you drain. Zero improvement means zero damage. This teaches a key lesson in drug discovery: <em>iterative improvement matters more than any single attempt</em>.",
      audio_text: "If your composite score is better than your previous best, you deal damage! The bigger the improvement, the more HP you drain. Zero improvement means zero damage. This teaches a key lesson in drug discovery: iterative improvement matters more than any single attempt.",
    },
    {
      title: "Winning the Battle",
      category: "Victory",
      visual: "victory",
      text: "Beat the <strong>win threshold score</strong> and the boss is defeated! For Level 1 on Junior difficulty, you need a composite score of <em>72%</em>. You earn XP points and a special boss badge. Each victory can unlock harder bosses. Your battle history is saved so you can track your progress.",
      audio_text: "Beat the win threshold score and the boss is defeated! For Level 1 on Junior difficulty, you need a composite score of seventy-two percent. You earn XP points and a special boss badge. Each victory can unlock harder bosses, and your battle history is saved.",
    },
    {
      title: "Choose Your Difficulty",
      category: "Difficulty",
      visual: "difficulty",
      text: "<strong>Scientist Junior</strong> — full reference drug as starting hint, unlimited attempts. <strong>Research Fellow</strong> — fragment hint only, 10 attempts. <strong>Principal Investigator</strong> — no hints, 5 attempts, must reach 80%. <strong>Nobel Prize</strong> — no hints, 3 rounds, 85% needed. Start with Junior and challenge yourself when ready!",
      audio_text: "Scientist Junior gives you the full reference drug as a starting hint with unlimited attempts. Research Fellow gives only a fragment with ten attempts. Principal Investigator gives no hints with five attempts. Nobel Prize is the ultimate challenge with three rounds and 85 percent required. Start with Junior!",
    },
    {
      title: "One Important Rule",
      category: "Science Ethics",
      visual: "disclaimer",
      text: "PathoHunt is always a <strong>computational simulation</strong>. A high score here means you have learned how drug discovery algorithms work — it does <em>not</em> mean you have discovered a real drug. Real drug development takes years of laboratory experiments, clinical trials, and safety testing. You are learning the first computational step. <strong>Now go defeat some pathogens!</strong>",
      audio_text: "PathoHunt is always a computational simulation. A high score here means you have learned how drug discovery algorithms work — it does not mean you have discovered a real drug. Real drug development takes years of laboratory experiments and clinical trials. You are learning the first computational step. Now go defeat some pathogens!",
    },
  ];

  /* ── State ─────────────────────────────────────────────────────────────── */
  let cur = 0;
  let playing = false;
  let muted = false;
  let audioEl = null;
  let audioCache = {};   // step index → blob URL
  let loadingAudio = false;

  /* ── Init ──────────────────────────────────────────────────────────────── */
  function init() {
    audioEl = document.getElementById('tutAudio');
    if (audioEl) {
      audioEl.onended = onAudioEnded;
      audioEl.onerror = onAudioError;
    }
    buildDots();
    renderStep(0);
    setupKeyboard();
    // Pre-fetch step 0 audio silently
    prefetchAudio(0);
  }

  /* ── Dots ──────────────────────────────────────────────────────────────── */
  function buildDots() {
    const container = document.getElementById('tutDots');
    if (!container) return;
    container.innerHTML = '';
    STEPS.forEach((_, i) => {
      const d = document.createElement('div');
      d.className = 'tut-dot' + (i === 0 ? ' active' : '');
      d.onclick = () => goTo(i);
      container.appendChild(d);
    });
  }

  function updateDots() {
    document.querySelectorAll('.tut-dot').forEach((d, i) => {
      d.className = 'tut-dot' +
        (i === cur ? ' active' : i < cur ? ' done' : '');
    });
  }

  /* ── Render ────────────────────────────────────────────────────────────── */
  function renderStep(idx) {
    const step = STEPS[idx];
    if (!step) return;

    // Category + title
    const catEl = document.getElementById('tutCategory');
    const titleEl = document.getElementById('tutTitle');
    if (catEl) catEl.textContent = step.category;
    if (titleEl) {
      titleEl.textContent = '';
      typewriter(titleEl, step.title);
    }

    // Bubble text
    const bubble = document.getElementById('tutBubble');
    if (bubble) bubble.innerHTML = step.text;

    // Progress bar
    const pct = ((idx) / (STEPS.length - 1)) * 100;
    const fill = document.getElementById('tutProgressFill');
    if (fill) fill.style.width = pct + '%';

    // Counter
    const counter = document.getElementById('tutCounter');
    if (counter) counter.textContent = `Step ${idx + 1} of ${STEPS.length}`;

    // Visual
    renderVisual(step.visual, idx);

    // Nav buttons
    document.getElementById('tutPrev').disabled = idx === 0;
    document.getElementById('tutNext').textContent =
      idx === STEPS.length - 1 ? '🎮 Start Playing!' : 'Next →';

    // Dots
    updateDots();
  }

  /* ── Visual renderer ─────────────────────────────────────────────────── */
  function renderVisual(type, stepIdx) {
    const container = document.getElementById('tutVisualContent');
    if (!container) return;
    container.innerHTML = '';

    switch (type) {
      case 'bosses':     renderBossesVisual(container); break;
      case 'hpbar':      renderHpBarVisual(container); break;
      case 'smiles':     renderSmilesVisual(container); break;
      case 'ai_flow':    renderAIFlowVisual(container); break;
      case 'scoring':    renderScoringVisual(container); break;
      case 'damage':     renderDamageVisual(container); break;
      case 'victory':    renderVictoryVisual(container); break;
      case 'difficulty': renderDifficultyVisual(container); break;
      case 'disclaimer': renderDisclaimerVisual(container); break;
      default:           container.innerHTML = '<div style="color:var(--muted)">—</div>';
    }
  }

  function renderBossesVisual(c) {
    const bosses = [
      { emoji: '🤧', name: 'Flu Commander', level: 1 },
      { emoji: '🦠', name: 'Corona Cutter', level: 2 },
      { emoji: '🔴', name: 'HIV Hydra', level: 3 },
      { emoji: '🧬', name: 'EGFR Enforcer', level: 4 },
      { emoji: '⚡', name: 'Mutant BRAF', level: 5 },
      { emoji: '⏳', name: 'Aging Architect', level: 6 },
      { emoji: '🔥', name: 'CDK2 Overlord', level: 7 },
    ];
    const wrap = document.createElement('div');
    wrap.className = 'vis-boss-float';
    bosses.forEach(b => {
      const el = document.createElement('div');
      el.className = 'vis-boss-bubble';
      el.innerHTML = `<span>${b.emoji}</span><span style="font-size:0.78rem;">Lv${b.level} ${b.name}</span>`;
      wrap.appendChild(el);
    });
    c.appendChild(wrap);
  }

  function renderHpBarVisual(c) {
    const wrap = document.createElement('div');
    wrap.className = 'vis-hp-demo';
    wrap.innerHTML = `
      <div class="vis-hp-label">
        <span>Boss: Flu Commander</span>
        <span id="visHpPct">38%</span>
      </div>
      <div class="vis-hp-track"><div class="vis-hp-bar" id="visHpBar" style="width:38%;">Simulation HP: 38%</div></div>
      <div style="font-size:0.75rem;color:var(--muted);font-style:italic;">Computer simulation only — not a real viral infection</div>
      <div style="margin-top:12px;font-size:0.82rem;color:var(--muted);">
        <div>Known drug (Oseltamivir) already brings boss to 38%.</div>
        <div>Your goal: push it lower with a better molecule.</div>
      </div>
    `;
    c.appendChild(wrap);
    // Animate HP bar after a delay
    setTimeout(() => {
      const bar = document.getElementById('visHpBar');
      const pct = document.getElementById('visHpPct');
      if (bar) { bar.style.width = '38%'; bar.textContent = 'Simulation HP: 38%'; }
    }, 100);
    // Animate it depleting
    setTimeout(() => {
      const bar = document.getElementById('visHpBar');
      const pct = document.getElementById('visHpPct');
      if (bar) { bar.style.width = '10%'; bar.textContent = 'Simulation HP: 10%'; }
      if (pct) pct.textContent = '10%';
    }, 1200);
    setTimeout(() => {
      const bar = document.getElementById('visHpBar');
      const pct = document.getElementById('visHpPct');
      if (bar) { bar.style.width = '0%'; bar.textContent = ''; bar.classList.add('low'); }
      if (pct) pct.textContent = '0%';
    }, 2600);
    setTimeout(() => {
      const bar = document.getElementById('visHpBar');
      const pct = document.getElementById('visHpPct');
      if (bar) { bar.style.width = '38%'; bar.textContent = 'Simulation HP: 38%'; bar.classList.remove('low'); }
      if (pct) pct.textContent = '38%';
    }, 4500);
  }

  function renderSmilesVisual(c) {
    const wrap = document.createElement('div');
    wrap.className = 'vis-smiles-box';
    wrap.innerHTML = `
      <div style="font-size:0.78rem;color:var(--muted);margin-bottom:6px;">Example: Oseltamivir (Tamiflu) — simplified</div>
      <div class="vis-smiles-str">
        <span class="sm-c">C</span><span class="sm-c">C</span><span class="sm-bond">(=</span><span class="sm-o">O</span><span class="sm-bond">)</span><span class="sm-ring">[N</span><span class="sm-c">H</span><span class="sm-ring">]</span><span class="sm-c">c1</span><span class="sm-c">cc</span><span class="sm-ring">(</span><span class="sm-o">O</span><span class="sm-ring">)</span><span class="sm-c">cc</span><span class="sm-c">c1</span>
      </div>
      <div style="display:flex;gap:16px;margin-top:12px;flex-wrap:wrap;">
        <div style="font-size:0.75rem;"><span style="color:#e5e7eb;">C</span> = Carbon</div>
        <div style="font-size:0.75rem;"><span style="color:#60a5fa;">N</span> = Nitrogen</div>
        <div style="font-size:0.75rem;"><span style="color:#f87171;">O</span> = Oxygen</div>
        <div style="font-size:0.75rem;"><span style="color:#a78bfa;">[ ]</span> = Ring atom</div>
        <div style="font-size:0.75rem;"><span style="color:#4ade80;">=</span> = Double bond</div>
      </div>
      <div style="margin-top:10px;font-size:0.8rem;background:rgba(88,166,255,0.07);border-left:3px solid #58a6ff;border-radius:0 6px 6px 0;padding:8px 12px;color:var(--muted);">
        On Junior difficulty, the known drug SMILES is pre-filled for you!
      </div>
    `;
    c.appendChild(wrap);
  }

  function renderAIFlowVisual(c) {
    const wrap = document.createElement('div');
    wrap.className = 'vis-ai-flow';
    const seed = document.createElement('div');
    seed.innerHTML = '<div style="font-size:0.72rem;color:var(--muted);margin-bottom:4px;">Seed</div><div class="vis-mol-chip">CC(=O)Nc1…</div>';
    wrap.appendChild(seed);

    const arrow = document.createElement('div');
    arrow.className = 'vis-ai-arrow';
    arrow.innerHTML = '→<br><span style="font-size:0.65rem;color:var(--muted);">Gemma4</span>';
    wrap.appendChild(arrow);

    const mols = [
      { smi: 'CC(N)c1…', best: false, delay: 0.2 },
      { smi: 'CNC(=O)…', best: false, delay: 0.5 },
      { smi: 'CCc1cc…',  best: true,  delay: 0.8 },
      { smi: 'C1CCNC…', best: false, delay: 1.1 },
      { smi: 'Cc1ccc…', best: false, delay: 1.4 },
    ];
    const molWrap = document.createElement('div');
    molWrap.style.cssText = 'display:flex;flex-direction:column;gap:5px;';
    mols.forEach(m => {
      const chip = document.createElement('div');
      chip.className = 'vis-mol-chip' + (m.best ? ' best' : '');
      chip.style.animationDelay = m.delay + 's';
      chip.textContent = m.smi + (m.best ? ' ★ Best' : '');
      molWrap.appendChild(chip);
    });
    wrap.appendChild(molWrap);
    c.appendChild(wrap);
  }

  function renderScoringVisual(c) {
    const wrap = document.createElement('div');
    wrap.className = 'vis-score-breakdown';
    const rows = [
      { name: 'QED', pct: 73, color: '#4ade80',  label: '0.73', desc: 'Drug-likeness' },
      { name: 'SAS', pct: 65, color: '#60a5fa',  label: '3.2',  desc: 'Synth. ease' },
      { name: 'Tanimoto', pct: 58, color: '#a78bfa', label: '0.58', desc: 'Similarity' },
    ];
    rows.forEach(r => {
      const row = document.createElement('div');
      row.className = 'vis-score-row';
      row.innerHTML = `
        <div class="vis-score-name">${r.name}</div>
        <div class="vis-score-track">
          <div class="vis-score-fill" style="width:0%;background:${r.color};" data-pct="${r.pct}"></div>
        </div>
        <div class="vis-score-val" style="color:${r.color};">${r.label}</div>
        <div style="width:90px;font-size:0.72rem;color:var(--muted);">${r.desc}</div>
      `;
      wrap.appendChild(row);
    });
    // Composite row
    const comp = document.createElement('div');
    comp.style.cssText = 'margin-top:10px;font-size:0.85rem;font-weight:700;padding:8px 12px;background:rgba(74,222,128,0.1);border-radius:6px;color:#4ade80;';
    comp.textContent = '→ Composite Score: 68%';
    wrap.appendChild(comp);
    c.appendChild(wrap);
    // Animate bars
    setTimeout(() => {
      wrap.querySelectorAll('.vis-score-fill').forEach(el => {
        el.style.width = el.dataset.pct + '%';
      });
    }, 300);
  }

  function renderDamageVisual(c) {
    const wrap = document.createElement('div');
    wrap.className = 'vis-damage-demo';
    wrap.innerHTML = `
      <div style="font-size:0.78rem;color:var(--muted);margin-bottom:6px;">Attack #2 — Previous best: 60% → New: 68%</div>
      <div class="vis-hp-track" style="margin-bottom:8px;">
        <div class="vis-hp-bar" id="visDmgHp" style="width:22%;">HP: 22%</div>
      </div>
      <div style="font-size:0.82rem;margin-top:6px;display:flex;gap:16px;">
        <span style="color:#4ade80;">▲ Improvement: +8%</span>
        <span style="color:#4ade80;">💥 Damage: 8 HP</span>
      </div>
      <div style="margin-top:8px;font-size:0.82rem;color:var(--muted);">
        Attack #3 — Same score as before: <span style="color:#6b7280;">No damage (0 HP)</span>
      </div>
    `;
    // Spawn damage pop
    setTimeout(() => {
      const pop = document.createElement('div');
      pop.className = 'vis-dmg-pop';
      pop.textContent = '−8 HP!';
      wrap.appendChild(pop);
      const bar = document.getElementById('visDmgHp');
      if (bar) { bar.style.width = '14%'; bar.textContent = 'HP: 14%'; }
      setTimeout(() => pop.remove(), 2000);
    }, 800);
    c.appendChild(wrap);
  }

  function renderVictoryVisual(c) {
    const wrap = document.createElement('div');
    wrap.className = 'vis-win-list';
    const items = [
      { text: 'Composite score ≥ 72% (Junior)', done: true },
      { text: 'Better than the known drug baseline', done: true },
      { text: 'Lipinski drug-likeness rules pass', done: true },
      { text: 'XP awarded: +100 XP', done: true },
      { text: 'Badge unlocked: 🤧 Flu Slayer', done: true },
    ];
    items.forEach((item, i) => {
      const row = document.createElement('div');
      row.className = 'vis-win-item';
      row.innerHTML = `<div class="vis-win-check" id="wc${i}">✓</div><span>${item.text}</span>`;
      wrap.appendChild(row);
    });
    // Animate checks appearing
    items.forEach((item, i) => {
      setTimeout(() => {
        const el = document.getElementById(`wc${i}`);
        if (el) el.classList.add('done');
      }, i * 300 + 400);
    });
    // Big win label
    const win = document.createElement('div');
    win.style.cssText = 'text-align:center;font-size:1.4rem;font-weight:800;color:#4ade80;margin-top:10px;';
    win.textContent = '🏆 VICTORY!';
    wrap.appendChild(win);
    c.appendChild(wrap);
  }

  function renderDifficultyVisual(c) {
    const wrap = document.createElement('div');
    wrap.className = 'vis-diff-tiers';
    const tiers = [
      { label: 'Scientist Junior', cls: 'diff-junior', hint: 'Full drug hint + unlimited tries', threshold: '70%' },
      { label: 'Research Fellow',  cls: 'diff-fellow', hint: 'Fragment only, 10 attempts',      threshold: '75%' },
      { label: 'Principal Investigator', cls: 'diff-pi', hint: 'No hint, 5 attempts',          threshold: '80%' },
      { label: 'Nobel Prize',      cls: 'diff-nobel',  hint: 'No hint, 3 rounds, hardest',     threshold: '85%' },
    ];
    tiers.forEach(t => {
      const row = document.createElement('div');
      row.className = 'vis-diff-row';
      row.innerHTML = `
        <div class="vis-diff-badge diff-pill ${t.cls}">${t.label}</div>
        <div style="flex:1;font-size:0.78rem;color:var(--muted);">${t.hint}</div>
        <div style="font-size:0.78rem;font-weight:700;color:var(--text);">≥${t.threshold}</div>
      `;
      wrap.appendChild(row);
    });
    c.appendChild(wrap);
  }

  function renderDisclaimerVisual(c) {
    const wrap = document.createElement('div');
    wrap.className = 'vis-disclaimer';
    wrap.innerHTML = `
      <div style="font-size:1rem;font-weight:700;color:#ffa657;margin-bottom:8px;">⚠️ Always Remember</div>
      <ul style="padding-left:18px;font-size:0.85rem;color:var(--muted);line-height:1.7;">
        <li>PathoHunt uses <strong style="color:var(--text);">real cheminformatics algorithms</strong></li>
        <li>A high game score = <strong style="color:var(--text);">you learned the method</strong></li>
        <li>It does <em>not</em> mean you found a real drug candidate</li>
        <li>Real drug approval takes 12–15 years of research</li>
        <li>Use the platform to <strong style="color:#4ade80;">understand how scientists think</strong></li>
      </ul>
      <div style="margin-top:12px;text-align:center;font-size:1.1rem;font-weight:700;color:#4ade80;">
        Ready to start? → Choose Level 1: Flu Commander 🤧
      </div>
    `;
    c.appendChild(wrap);
  }

  /* ── TTS / Audio ─────────────────────────────────────────────────────── */
  async function prefetchAudio(idx) {
    if (muted || audioCache[idx] || loadingAudio) return;
    const step = STEPS[idx];
    if (!step) return;
    loadingAudio = true;
    try {
      const res = await fetch('/api/v3/game/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: step.audio_text, voice: 'am_michael' }),
      });
      if (res.ok) {
        const blob = await res.blob();
        audioCache[idx] = URL.createObjectURL(blob);
      }
    } catch (_) { /* silent — TTS is optional */ }
    loadingAudio = false;
  }

  async function playCurrentAudio() {
    if (muted || !audioEl) return;
    const idx = cur;

    setAvatarSpeaking(true);
    setWavesActive(true);

    // Show loading if audio not cached
    if (!audioCache[idx]) {
      showTutLoading(true);
      await prefetchAudio(idx);
      showTutLoading(false);
    }

    const src = audioCache[idx];
    if (!src) {
      // No audio — fall back to text-timing
      setAvatarSpeaking(false);
      setWavesActive(false);
      return;
    }

    audioEl.src = src;
    try {
      await audioEl.play();
    } catch (_) {
      setAvatarSpeaking(false);
      setWavesActive(false);
    }

    // Pre-fetch next
    prefetchAudio(idx + 1);
  }

  function onAudioEnded() {
    setAvatarSpeaking(false);
    setWavesActive(false);
    if (playing && cur < STEPS.length - 1) {
      setTimeout(() => goTo(cur + 1), 400);
    } else if (cur >= STEPS.length - 1) {
      playing = false;
      updatePlayBtn();
    }
  }

  function onAudioError() {
    setAvatarSpeaking(false);
    setWavesActive(false);
    if (playing && cur < STEPS.length - 1) {
      const dur = Math.max(3000, (STEPS[cur]?.audio_text?.length || 100) * 60);
      setTimeout(() => goTo(cur + 1), dur);
    }
  }

  /* ── Navigation ──────────────────────────────────────────────────────── */
  function goTo(idx) {
    if (idx < 0 || idx >= STEPS.length) return;
    stopAudio();
    cur = idx;
    renderStep(idx);
    if (playing) {
      playCurrentAudio();
    }
    // Prefetch next
    prefetchAudio(idx + 1);
  }

  window.tutNext = function () {
    if (cur >= STEPS.length - 1) {
      window.location.href = '/game';
    } else {
      playing = false;
      stopAudio();
      goTo(cur + 1);
      updatePlayBtn();
    }
  };

  window.tutPrev = function () {
    playing = false;
    stopAudio();
    goTo(cur - 1);
    updatePlayBtn();
  };

  window.tutTogglePlay = function () {
    playing = !playing;
    updatePlayBtn();
    if (playing) {
      playCurrentAudio();
    } else {
      stopAudio();
    }
  };

  window.tutToggleMute = function () {
    muted = !muted;
    const btn = document.getElementById('tutMuteBtn');
    if (btn) {
      btn.textContent = muted ? '🔇 Unmute' : '🔊 Mute';
      btn.classList.toggle('muted', muted);
    }
    if (muted) stopAudio();
  };

  /* ── Helpers ─────────────────────────────────────────────────────────── */
  function stopAudio() {
    if (audioEl) { audioEl.pause(); audioEl.src = ''; }
    setAvatarSpeaking(false);
    setWavesActive(false);
    showTutLoading(false);
  }

  function setAvatarSpeaking(on) {
    const el = document.getElementById('tutHostAvatar');
    if (el) el.classList.toggle('speaking', on);
  }

  function setWavesActive(on) {
    const el = document.getElementById('tutWaves');
    if (el) el.classList.toggle('active', on);
  }

  function showTutLoading(on) {
    const el = document.getElementById('tutLoading');
    if (el) el.classList.toggle('active', on);
  }

  function updatePlayBtn() {
    const btn = document.getElementById('tutPlayBtn');
    if (btn) btn.textContent = playing ? '⏸ Pause' : '▶ Play';
  }

  function typewriter(el, text) {
    el.textContent = '';
    let i = 0;
    const tick = () => {
      el.textContent = text.slice(0, ++i);
      if (i < text.length) setTimeout(tick, 28);
    };
    tick();
  }

  /* ── Keyboard ─────────────────────────────────────────────────────────── */
  function setupKeyboard() {
    document.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight') { playing = false; stopAudio(); updatePlayBtn(); tutNext(); }
      if (e.key === 'ArrowLeft')  { playing = false; stopAudio(); updatePlayBtn(); tutPrev(); }
      if (e.key === ' ')          { e.preventDefault(); tutTogglePlay(); }
      if (e.key === 'm' || e.key === 'M') tutToggleMute();
    });
  }

  /* ── Boot ─────────────────────────────────────────────────────────────── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
