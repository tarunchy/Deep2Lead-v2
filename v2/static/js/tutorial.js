// ── Section narrations (plain text — no special chars for Kokoro) ──
const NARRATIONS = [
  // S1
  "Welcome to Deep2Lead. Traditional drug development takes over 10 years and costs up to 2.6 billion dollars, with 90 percent of clinical candidates failing. Deep2Lead uses Gemma4, an AI model running on NVIDIA DGX hardware, to generate and score novel drug candidates in seconds. In this 8-section tutorial you will learn the chemistry behind drug discovery, how to read SMILES strings and protein sequences, and how to use every feature of the platform.",
  // S2
  "All chemistry is about electrons. Atoms form bonds by sharing or transferring valence electrons. There are four types of chemical bonds. Covalent bonds are extremely strong and usually irreversible. Ionic interactions are strong and reversible. Hydrogen bonds are moderate and very common in biological systems. Van der Waals forces are weak but collectively powerful. Most drugs bind their protein target using combinations of hydrogen bonds and Van der Waals forces, allowing them to bind, trigger a biological response, and safely depart.",
  // S3
  "SMILES stands for Simplified Molecular Input Line Entry System. It encodes a molecule as a plain text string. Capital letters represent atoms: C for carbon, N for nitrogen, O for oxygen, S for sulfur. Lowercase letters like c and n represent aromatic ring atoms. Parentheses show branches off the main chain, and numbers mark where rings close. For example, aspirin is written as C C, open paren, equals O, close paren, O, c1ccccc1, C, open paren, equals O, close paren, O. You can paste any valid SMILES into Deep2Lead as your seed molecule.",
  // S4
  "Proteins are chains of amino acids. There are 20 standard amino acids, each with a unique single-letter code. A is Alanine, C is Cysteine, D is Aspartic acid, E is Glutamic acid, F is Phenylalanine, G is Glycine, H is Histidine, I is Isoleucine, K is Lysine, L is Leucine, M is Methionine, N is Asparagine, P is Proline, Q is Glutamine, R is Arginine, S is Serine, T is Threonine, V is Valine, W is Tryptophan, and Y is Tyrosine. Deep2Lead accepts any sequence using these 20 standard codes.",
  // S5
  "Deep2Lead computes six properties for every candidate. QED ranges from 0 to 1, where 1 means perfectly drug-like. SAS ranges from 1 to 10, where 1 means very easy to synthesize. LogP ideally falls between 0 and 3 for oral bioavailability. Molecular weight should stay below 500 Daltons. Tanimoto similarity measures structural closeness to your seed from 0 to 1. Lipinski pass or fail checks four simple rules for oral drugs. The composite score combines DTI at 35 percent, QED at 30 percent, inverse SAS at 20 percent, and Tanimoto at 15 percent.",
  // S6
  "Running an experiment takes six steps. First, go to Run Experiment. Second, paste your protein target amino acid sequence. Third, enter your seed SMILES and watch the molecule preview appear. Fourth, set the diversity slider. Low diversity gives close structural analogs of the seed. High diversity explores more distant chemical space. Fifth, choose how many candidates to generate and click Generate. Gemma4 returns results in under a minute. Sixth, add a title and hypothesis in the Save and Publish panel, then publish to share with your class.",
  // S7
  "Your results table shows candidates ranked by composite score, with rank 1 highlighted. Each row shows the composite score, DTI, QED, SAS, LogP, molecular weight, Tanimoto similarity, and Lipinski pass or fail. A strong candidate typically scores above 0.5 overall, has QED above 0.6, SAS below 4, LogP between 0 and 3, passes Lipinski, and has Tanimoto between 0.3 and 0.7. Click View to see the molecular structure diagram. Click Copy to export the SMILES for external tools like Schrodinger or AutoDock.",
  // S8
  "Publishing adds your experiment to the class feed where classmates can review and comment. Use the AI Suggest button to let Gemma4 draft a title and hypothesis based on your results. A good hypothesis names the seed molecule, describes the structural modification, and explains the chemical rationale for why it might improve binding. Classmates can post tagged comments: questions to ask for clarification, suggestions to propose alternatives, corrections to point out errors, and praise to acknowledge strong reasoning. Respond to build a scientific discussion."
];

const TOTAL_SECTIONS = 8;
let current = 1;
let audioObj = null;
let audioLoading = false;
let audioPlaying = false;

// ── Navigation ──────────────────────────────────────────────────────
function navigate(delta) {
  goTo(current + delta);
}

function goTo(n) {
  if (n < 1 || n > TOTAL_SECTIONS) return;
  document.querySelector(`[data-section="${current}"]`).style.display = "none";
  current = n;
  document.querySelector(`[data-section="${current}"]`).style.display = "block";
  updateProgress();
  updateNav();
  stopAudio();
  window.scrollTo({ top: 0, behavior: "smooth" });

  if (n === TOTAL_SECTIONS) {
    setTimeout(() => {
      document.getElementById("complete-banner").style.display = "block";
    }, 800);
  }
}

function updateProgress() {
  const pct = (current / TOTAL_SECTIONS) * 100;
  document.getElementById("tut-progress").style.width = pct + "%";
  document.getElementById("tut-section-label").textContent = `Section ${current} of ${TOTAL_SECTIONS}`;
}

function updateNav() {
  document.getElementById("nav-prev").disabled = current === 1;
  const nextBtn = document.getElementById("nav-next");
  nextBtn.textContent = current === TOTAL_SECTIONS ? "Finish ✓" : "Next →";
  if (current === TOTAL_SECTIONS) {
    nextBtn.onclick = () => { window.location.href = "/run"; };
  } else {
    nextBtn.onclick = () => navigate(1);
  }
}

// ── Audio ───────────────────────────────────────────────────────────
async function toggleAudio() {
  if (audioLoading) return;
  if (audioPlaying && audioObj) {
    stopAudio();
    return;
  }
  await playNarration(current);
}

async function playNarration(sectionIdx) {
  stopAudio();
  audioLoading = true;
  setAudioBtn("loading");

  const text = NARRATIONS[sectionIdx - 1];
  try {
    const resp = await fetch("/api/v2/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice: "af_heart", speed: 0.92 }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || "TTS unavailable");
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    audioObj = new Audio(url);
    audioObj.onended = () => {
      audioPlaying = false;
      setAudioBtn("idle");
      URL.revokeObjectURL(url);
    };
    audioObj.onerror = () => {
      audioPlaying = false;
      setAudioBtn("idle");
    };
    audioObj.play();
    audioPlaying = true;
    setAudioBtn("playing");
  } catch (err) {
    showAlert("Audio unavailable: " + err.message, "error", document.body);
    setAudioBtn("idle");
  } finally {
    audioLoading = false;
  }
}

function stopAudio() {
  if (audioObj) {
    audioObj.pause();
    audioObj.src = "";
    audioObj = null;
  }
  audioPlaying = false;
  audioLoading = false;
  setAudioBtn("idle");
}

function setAudioBtn(state) {
  const icon = document.getElementById("audio-icon");
  const label = document.getElementById("audio-label");
  const btn = document.getElementById("audio-btn");
  if (state === "loading") {
    icon.textContent = "⏳"; label.textContent = "Loading…"; btn.disabled = true;
  } else if (state === "playing") {
    icon.textContent = "⏸"; label.textContent = "Pause"; btn.disabled = false;
  } else {
    icon.textContent = "🔊"; label.textContent = "Listen"; btn.disabled = false;
  }
}

// ── Quiz ────────────────────────────────────────────────────────────
function checkAnswer(btn, chosen, correct) {
  const quiz = btn.closest(".tut-quiz");
  const feedback = quiz.querySelector(".tut-quiz-feedback");
  quiz.querySelectorAll("button").forEach(b => {
    b.disabled = true;
    const val = b.getAttribute("onclick").match(/'([A-C])'/)?.[1];
    if (val === correct) b.classList.add("correct");
  });
  if (chosen === correct) {
    btn.classList.add("correct");
    feedback.textContent = "Correct!";
    feedback.style.display = "block";
    feedback.style.color = "var(--success)";
    feedback.style.background = "#f0fff4";
  } else {
    btn.classList.add("wrong");
    feedback.textContent = "Not quite — the highlighted answer is correct.";
    feedback.style.display = "block";
    feedback.style.color = "var(--danger)";
    feedback.style.background = "#fff5f5";
  }
}

// ── Clipboard helpers ───────────────────────────────────────────────
function copyMol(elId) {
  const text = document.getElementById(elId).textContent.trim();
  navigator.clipboard.writeText(text).then(() =>
    showAlert("SMILES copied to clipboard", "success", document.body)
  );
}

function copySeq(elId) {
  const text = document.getElementById(elId).textContent.trim();
  navigator.clipboard.writeText(text).then(() =>
    showAlert("Sequence copied to clipboard", "success", document.body)
  );
}

// ── Try in App (pre-fill run page via localStorage) ─────────────────
function tryInApp(smile, aminoAcid) {
  if (smile) localStorage.setItem("d2l_prefill_smile", smile);
  if (aminoAcid) localStorage.setItem("d2l_prefill_aa", aminoAcid);
  window.location.href = "/run";
}

// ── Init ────────────────────────────────────────────────────────────
updateProgress();
updateNav();
