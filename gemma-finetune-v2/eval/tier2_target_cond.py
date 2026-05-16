"""
Tier 2 — Target-conditioned generation and MAMMAL affinity scoring.

For each held-out target:
  1. Prompt the model with the target FASTA + design task
  2. Extract generated SMILES
  3. Score each via MAMMAL pKd API (dlyog03:8090)
  4. Also score known drugs as positive controls

Paper metrics (Table 2):
  - Mean pKd of generated molecules per target
  - % is_binder (pKd >= 7.0)
  - Per-target diversity
  - Delta pKd vs known drug (positive control gap)
  - Scaffold variety (number of distinct Murcko scaffolds)
"""

import statistics
import torch
from typing import Optional

from eval.eval_utils import (
    extract_smiles_from_text, mammal_score_batch, mammal_available,
    internal_diversity, canonical,
)
from eval.held_out_targets import HELD_OUT_TARGETS


def _murcko_scaffold(smiles: str) -> Optional[str]:
    try:
        from rdkit.Chem.Scaffolds import MurckoScaffold
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
    except Exception:
        return None


def _generate_for_target(model, processor, target: dict, n_per_target: int, device: str) -> list[str]:
    prompt = target["prompt_template"].format(fasta=target["fasta"])
    messages = [
        {"role": "system",    "content": [{"type": "text", "text": (
            "You are Deep2Lead's drug discovery AI v2. Reason about binding pocket geometry "
            "and physicochemical requirements (label as 'Rationale:'), then output novel "
            "drug-like SMILES (label each as 'SMILES:'). Be specific and chemically accurate."
        )}]},
        {"role": "user",      "content": [{"type": "text", "text": prompt}]},
    ]
    # Generate multiple times to get n_per_target diverse outputs
    all_smiles = []
    n_calls = max(1, n_per_target // 4)   # each call yields ~4 SMILES on average
    for _ in range(n_calls):
        inputs = processor.apply_chat_template(
            messages, add_generation_prompt=True,
            return_tensors="pt", return_dict=True, tokenize=True,
        ).to(device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.90,
                top_p=0.92,
                top_k=50,
                repetition_penalty=1.2,
            )
        generated_ids = outputs[0][inputs["input_ids"].shape[-1]:]
        text = processor.decode(generated_ids, skip_special_tokens=True).strip()
        smiles = extract_smiles_from_text(text)
        all_smiles.extend(smiles)

    # Deduplicate and cap
    seen = set()
    unique = []
    for s in all_smiles:
        c = canonical(s)
        if c and c not in seen:
            seen.add(c)
            unique.append(c)
    return unique[:n_per_target]


def run_tier2(
    model,
    processor,
    n_per_target: int = 20,
    device: str = "cuda",
    skip_mammal: bool = False,
) -> list[dict]:
    """
    Run Tier 2 for all held-out targets. Returns list of per-target result dicts.
    """
    mammal_ok = mammal_available() and not skip_mammal
    if not mammal_ok:
        print("  [Tier2] MAMMAL API not reachable — pKd scores will be skipped.")

    per_target_results = []

    for target in HELD_OUT_TARGETS:
        name = target["name"]
        print(f"\n  [Tier2] Target: {name}")

        # 1. Generate SMILES
        gen_smiles = _generate_for_target(model, processor, target, n_per_target, device)
        print(f"    Generated: {len(gen_smiles)} unique valid SMILES")

        # 2. MAMMAL scoring for generated molecules
        gen_scores = []
        if mammal_ok and gen_smiles:
            gen_scores = mammal_score_batch(target["fasta"], gen_smiles)
            pkds = [r["pkd"] for r in gen_scores if r["pkd"] is not None]
            n_binder = sum(1 for r in gen_scores if r.get("is_binder"))
            print(f"    pKd: mean={statistics.mean(pkds):.3f} max={max(pkds):.3f} | "
                  f"is_binder: {n_binder}/{len(gen_smiles)}")

        # 3. Score known drugs as positive controls
        known_scores = []
        if mammal_ok and target.get("known_drugs"):
            known_scores = mammal_score_batch(target["fasta"], target["known_drugs"])
            for ks in known_scores:
                print(f"    Known drug pKd: {ks.get('pkd', 'N/A'):.3f}"
                      if ks.get("pkd") is not None else "    Known drug: API error")

        # 4. Scaffold diversity
        scaffolds = [_murcko_scaffold(s) for s in gen_smiles]
        n_scaffolds = len(set(s for s in scaffolds if s))

        # 5. Aggregate
        pkds_gen   = [r["pkd"] for r in gen_scores if r.get("pkd") is not None]
        pkds_known = [r["pkd"] for r in known_scores if r.get("pkd") is not None]

        result = {
            "target_name":      name,
            "disease":          target["disease"],
            "n_generated":      len(gen_smiles),
            "n_scaffolds":      n_scaffolds,
            "diversity":        round(internal_diversity(gen_smiles), 4),
            "generated_smiles": gen_smiles,
            "gen_mammal":       gen_scores,
            "known_mammal":     known_scores,
        }

        if pkds_gen:
            result.update({
                "mean_pkd":      round(statistics.mean(pkds_gen), 4),
                "max_pkd":       round(max(pkds_gen), 4),
                "std_pkd":       round(statistics.stdev(pkds_gen) if len(pkds_gen)>1 else 0.0, 4),
                "pct_binder":    round(sum(1 for r in gen_scores if r.get("is_binder")) / len(gen_smiles), 4),
            })
        if pkds_gen and pkds_known:
            result["delta_pkd_vs_known"] = round(
                statistics.mean(pkds_gen) - statistics.mean(pkds_known), 4
            )

        per_target_results.append(result)

    return per_target_results


def print_tier2(results: list[dict]):
    print(f"\n{'='*70}")
    print(f"TIER 2 — Target-Conditioned Generation + MAMMAL Affinity Scoring")
    print(f"{'='*70}")
    print(f"{'Target':<35} {'N':>4} {'Scaffolds':>9} {'mean pKd':>9} {'%Binder':>8} {'Δ Known':>8}")
    print(f"{'-'*70}")
    for r in results:
        mean_pkd   = f"{r['mean_pkd']:.3f}"   if "mean_pkd"   in r else "  N/A  "
        pct_binder = f"{r['pct_binder']:.1%}" if "pct_binder" in r else "  N/A"
        delta      = f"{r['delta_pkd_vs_known']:+.3f}" if "delta_pkd_vs_known" in r else "  N/A"
        print(f"  {r['target_name']:<33} {r['n_generated']:>4} "
              f"{r['n_scaffolds']:>9} {mean_pkd:>9} {pct_binder:>8} {delta:>8}")
    print(f"{'='*70}")
