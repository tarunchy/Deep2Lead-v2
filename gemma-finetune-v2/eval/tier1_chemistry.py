"""
Tier 1 — Chemical validity and drug-likeness evaluation.

Metrics (paper Table 1):
  - SMILES validity        (% parseable by RDKit)
  - Uniqueness             (% non-duplicate)
  - Novelty                (% Tanimoto < 0.4 vs training set)
  - Internal diversity     (mean pairwise Tanimoto distance)
  - Lipinski Ro5 pass rate
  - QED distribution       (mean ± std)
  - SAS distribution       (mean ± std)  lower = better
  - MW distribution        (mean ± std)
  - LogP distribution      (mean ± std)
"""

import json
import statistics
from typing import Optional

from eval.eval_utils import (
    get_mol, qed, sas, lipinski, canonical,
    novelty_vs_set, internal_diversity,
)


def run_tier1(
    smiles_list: list[str],
    training_smiles: Optional[list[str]] = None,
    label: str = "model",
) -> dict:
    """
    Compute all Tier 1 metrics for a list of generated SMILES.

    Args:
        smiles_list:     generated SMILES (raw, may contain invalids)
        training_smiles: reference set for novelty computation
        label:           identifier for this run (e.g. "v1", "v2")

    Returns:
        dict of scalar metrics suitable for paper Table 1
    """
    if not smiles_list:
        return {"label": label, "error": "no_smiles"}

    total = len(smiles_list)

    # Validity + canonicalization
    valid_smiles = [canonical(s) for s in smiles_list]
    valid_smiles = [s for s in valid_smiles if s]
    n_valid      = len(valid_smiles)
    validity     = n_valid / total

    # Uniqueness
    unique_smiles = list(set(valid_smiles))
    uniqueness    = len(unique_smiles) / n_valid if n_valid else 0.0

    # QED
    qeds = [q for s in unique_smiles if (q := qed(s)) is not None]
    avg_qed = statistics.mean(qeds) if qeds else 0.0
    std_qed = statistics.stdev(qeds) if len(qeds) > 1 else 0.0

    # SAS
    sass = [v for s in unique_smiles if (v := sas(s)) is not None]
    avg_sas = statistics.mean(sass) if sass else 0.0
    std_sas = statistics.stdev(sass) if len(sass) > 1 else 0.0

    # Lipinski
    lip_results = [lipinski(s) for s in unique_smiles]
    ro5_pass  = sum(1 for r in lip_results if r.get("ro5_pass"))
    ro5_rate  = ro5_pass / len(unique_smiles) if unique_smiles else 0.0

    mws  = [r["mw"]   for r in lip_results if r.get("valid")]
    logps= [r["logp"] for r in lip_results if r.get("valid")]
    avg_mw   = statistics.mean(mws)   if mws   else 0.0
    avg_logp = statistics.mean(logps) if logps else 0.0

    # Novelty vs training set
    novelty = novelty_vs_set(unique_smiles, training_smiles or [], threshold=0.4)

    # Internal diversity
    div = internal_diversity(unique_smiles)

    result = {
        "label":             label,
        "total_generated":   total,
        "n_valid":           n_valid,
        "n_unique":          len(unique_smiles),
        "validity":          round(validity, 4),
        "uniqueness":        round(uniqueness, 4),
        "novelty":           round(novelty, 4),
        "internal_diversity":round(div, 4),
        "ro5_pass_rate":     round(ro5_rate, 4),
        "avg_qed":           round(avg_qed, 4),
        "std_qed":           round(std_qed, 4),
        "avg_sas":           round(avg_sas, 4),
        "std_sas":           round(std_sas, 4),
        "avg_mw":            round(avg_mw, 1),
        "avg_logp":          round(avg_logp, 3),
    }
    return result


def print_tier1(metrics: dict):
    label = metrics.get("label", "?")
    print(f"\n{'='*55}")
    print(f"TIER 1 — Chemical Quality  [{label}]")
    print(f"{'='*55}")
    print(f"  Generated / Valid / Unique: "
          f"{metrics['total_generated']} / {metrics['n_valid']} / {metrics['n_unique']}")
    print(f"  Validity:          {metrics['validity']:.1%}")
    print(f"  Uniqueness:        {metrics['uniqueness']:.1%}")
    print(f"  Novelty (Tc<0.4):  {metrics['novelty']:.1%}")
    print(f"  Internal diversity:{metrics['internal_diversity']:.3f}")
    print(f"  Lipinski Ro5:      {metrics['ro5_pass_rate']:.1%}")
    print(f"  QED:               {metrics['avg_qed']:.3f} ± {metrics['std_qed']:.3f}")
    print(f"  SAS:               {metrics['avg_sas']:.3f} ± {metrics['std_sas']:.3f}")
    print(f"  MW (Da):           {metrics['avg_mw']:.1f}")
    print(f"  LogP:              {metrics['avg_logp']:.3f}")
    print(f"{'='*55}")


def load_training_smiles(merged_jsonl: str) -> list[str]:
    """Extract SMILES from the merged training JSONL for novelty computation."""
    from data.dataset_utils import extract_smiles_from_text
    smiles = []
    try:
        with open(merged_jsonl) as f:
            for line in f:
                try:
                    row = json.loads(line)
                    for msg in row.get("messages", []):
                        if msg.get("role") == "assistant":
                            for blk in msg.get("content", []):
                                text = blk.get("text", "") if isinstance(blk, dict) else str(blk)
                                smiles.extend(extract_smiles_from_text(text))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return list(set(smiles))
