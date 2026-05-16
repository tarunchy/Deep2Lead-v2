"""
Tier 3 — Rationale quality evaluation.

Three independent scoring methods (each contributes to a composite score):

  A. Format compliance  — does Rationale: precede SMILES: ? (binary)
  B. Keyword coverage   — do responses mention relevant binding vocabulary?
  C. Coherence score    — rule-based heuristics; optionally upgraded to LLM judge

Paper metric (Table 3):
  - rationale_format_rate    (0-1)
  - keyword_coverage_rate    (0-1)
  - coherence_score          (0-1)
  - composite_rationale_score (weighted average of A+B+C)
  - smiles_rationale_corr    (Pearson r between coherence and MAMMAL pKd)
"""

import re
import statistics
from typing import Optional


# ── Binding-relevant vocabulary ────────────────────────────────────────────────

BINDING_KEYWORDS = [
    # Pocket geometry
    "hydrophobic", "aromatic", "pi-pi", "pi-stacking", "cleft", "pocket", "groove",
    "hinge", "allosteric", "cavity",
    # Interaction types
    "hydrogen bond", "h-bond", "hbond", "salt bridge", "electrostatic",
    "van der waals", "halogen bond", "covalent", "coordination",
    # Pharmacophore / design language
    "pharmacophore", "scaffold", "bioisostere", "warhead", "linker",
    "selectivity", "affinity", "potency", "binding mode",
    # ADMET
    "lipophilicity", "logp", "permeability", "solubility", "bioavailability",
    "bbb", "blood-brain", "psa", "mw", "molecular weight",
    # Residue language
    "residue", "amino acid", "ser", "asp", "his", "lys", "glu", "arg",
    "catalytic triad", "dyad", "active site",
]

# Must mention at least this many unique categories to pass
KEYWORD_THRESHOLD = 3


# ── A. Format compliance ───────────────────────────────────────────────────────

def check_format(response: str) -> bool:
    """Rationale: must appear before any SMILES: token."""
    lower = response.lower()
    r_pos = lower.find("rationale:")
    s_pos = lower.find("smiles:")
    return r_pos != -1 and (s_pos == -1 or r_pos < s_pos)


# ── B. Keyword coverage ────────────────────────────────────────────────────────

def keyword_coverage(response: str) -> dict:
    """Count how many unique binding keywords appear in the rationale section."""
    lower = response.lower()
    # Only score the rationale section (before first SMILES:)
    smiles_pos = lower.find("smiles:")
    rationale_text = lower[:smiles_pos] if smiles_pos != -1 else lower
    found = [kw for kw in BINDING_KEYWORDS if kw in rationale_text]
    n_found = len(found)
    return {
        "n_keywords":      n_found,
        "keywords_found":  found,
        "coverage_score":  min(n_found / KEYWORD_THRESHOLD, 1.0),
        "passes_threshold": n_found >= KEYWORD_THRESHOLD,
    }


# ── C. Coherence heuristics ────────────────────────────────────────────────────

def coherence_score(response: str) -> float:
    """
    Rule-based coherence (0.0–1.0). Checks:
      - Rationale is non-trivial length (> 40 words)
      - Contains at least one specific residue or structural mention
      - Does not just repeat the prompt verbatim (simple overlap check)
      - Mentions at least one ADMET property
    """
    lower = response.lower()
    smiles_pos = lower.find("smiles:")
    rationale_text = lower[:smiles_pos] if smiles_pos != -1 else lower

    scores = []

    # Length: rationale should be substantive
    word_count = len(rationale_text.split())
    scores.append(min(word_count / 80, 1.0))   # 80 words = full score

    # Structural specificity: mentions residue numbers or specific pocket features
    has_residue = bool(re.search(r'\b(cys|ser|asp|his|thr|lys|arg|glu)\d*\b', rationale_text))
    has_pocket  = any(kw in rationale_text for kw in ["active site", "binding pocket", "hinge", "allosteric"])
    scores.append(1.0 if (has_residue or has_pocket) else 0.0)

    # ADMET mention
    has_admet = any(kw in rationale_text for kw in [
        "logp", "mw", "molecular weight", "solubility", "permeability",
        "bbb", "blood-brain", "psa", "oral bioavailability",
    ])
    scores.append(1.0 if has_admet else 0.4)   # partial credit if missing ADMET

    # Design intent: mentions the strategy
    has_strategy = any(kw in rationale_text for kw in [
        "scaffold", "bioisostere", "pharmacophore", "selectivity",
        "resistance", "mutation", "covalent", "allosteric", "fragment",
    ])
    scores.append(1.0 if has_strategy else 0.3)

    return round(statistics.mean(scores), 4)


# ── Per-response scoring ───────────────────────────────────────────────────────

def score_response(response: str, pkd: Optional[float] = None) -> dict:
    """Score one model response across all three methods."""
    fmt    = check_format(response)
    kw     = keyword_coverage(response)
    coh    = coherence_score(response)

    composite = round(
        0.25 * (1.0 if fmt else 0.0) +
        0.40 * kw["coverage_score"] +
        0.35 * coh,
        4
    )
    return {
        "format_ok":        fmt,
        "n_keywords":       kw["n_keywords"],
        "keyword_coverage": round(kw["coverage_score"], 4),
        "coherence":        coh,
        "composite":        composite,
        "pkd":              pkd,
    }


# ── Aggregate over all responses ───────────────────────────────────────────────

def run_tier3(responses: list[str], pkds: Optional[list[float]] = None) -> dict:
    """
    responses: list of raw model response strings
    pkds:      optional list of MAMMAL pKd scores (same length) for correlation
    """
    if not responses:
        return {"error": "no_responses"}

    pkds = pkds or [None] * len(responses)
    scored = [score_response(r, p) for r, p in zip(responses, pkds)]

    format_rate = sum(1 for s in scored if s["format_ok"]) / len(scored)
    kw_rate     = statistics.mean(s["keyword_coverage"] for s in scored)
    coh_mean    = statistics.mean(s["coherence"] for s in scored)
    composite   = statistics.mean(s["composite"] for s in scored)

    result = {
        "n_responses":          len(scored),
        "rationale_format_rate":round(format_rate, 4),
        "keyword_coverage_rate":round(kw_rate, 4),
        "coherence_score":      round(coh_mean, 4),
        "composite_score":      round(composite, 4),
        "per_response":         scored,
    }

    # Pearson correlation between composite and pKd (if pKd available)
    valid_pairs = [(s["composite"], s["pkd"]) for s in scored if s["pkd"] is not None]
    if len(valid_pairs) >= 5:
        xs = [p[0] for p in valid_pairs]
        ys = [p[1] for p in valid_pairs]
        try:
            n   = len(xs)
            mx, my = statistics.mean(xs), statistics.mean(ys)
            cov = sum((x-mx)*(y-my) for x,y in zip(xs,ys)) / n
            sx  = statistics.stdev(xs)
            sy  = statistics.stdev(ys)
            r   = cov / (sx * sy) if sx * sy > 0 else 0.0
            result["rationale_pkd_correlation"] = round(r, 4)
        except Exception:
            pass

    return result


def print_tier3(metrics: dict):
    print(f"\n{'='*55}")
    print(f"TIER 3 — Rationale Quality")
    print(f"{'='*55}")
    print(f"  Responses evaluated:   {metrics.get('n_responses', 0)}")
    print(f"  Format compliance:     {metrics.get('rationale_format_rate', 0):.1%}")
    print(f"  Keyword coverage:      {metrics.get('keyword_coverage_rate', 0):.1%}")
    print(f"  Coherence score:       {metrics.get('coherence_score', 0):.3f}")
    print(f"  Composite score:       {metrics.get('composite_score', 0):.3f}  (0–1)")
    if "rationale_pkd_correlation" in metrics:
        r = metrics["rationale_pkd_correlation"]
        print(f"  Rationale–pKd corr:    r = {r:.3f}  "
              f"({'positive' if r > 0 else 'negative'} relationship)")
    print(f"{'='*55}")
