#!/usr/bin/env python3
"""
Side-by-side comparison: Production E2B (dlyog04:9000) vs Fine-tuned E2B (dgx1:9002).

Uses the EXACT same prompt as v2/services/molecule_generator.py so results are
directly comparable to what users see in the app.

Usage:
    python3 eval/compare_models.py
    python3 eval/compare_models.py --targets 3 --n 8
"""

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# ── Endpoints ──────────────────────────────────────────────────────────────────
PROD_URL      = "http://dlyog04:9000"   # production E2B — OpenAI format
FINETUNE_URL  = "http://dgx1:9002"      # fine-tuned E2B — custom format

TARGETS_JSON  = Path(__file__).parent.parent / "data" / "curated_targets.json"
TIMEOUT       = 120

# ── Same prompt as v2/services/molecule_generator.py ──────────────────────────
def build_prompt(seed_smiles: str, amino_acid_seq: str, noise: float = 0.5, n: int = 8) -> str:
    aa_preview = amino_acid_seq[:80] + ("..." if len(amino_acid_seq) > 80 else "")
    return (
        f"You are a computational chemistry assistant specializing in drug discovery.\n"
        f"Generate novel drug-like SMILES strings structurally similar to the seed molecule.\n\n"
        f"Seed SMILES: {seed_smiles}\n"
        f"Target protein (first 80 AA): {aa_preview}\n"
        f"Diversity level: {noise:.2f} (0=minimal change, 1=large structural variation)\n\n"
        f"Rules:\n"
        f"- Output ONLY valid SMILES strings, one per line, no numbering or explanation\n"
        f"- Each molecule must differ from the seed (substitute atoms, add/remove groups)\n"
        f"- Follow Lipinski's Rule of Five: MW<500, LogP<5, HBD<=5, HBA<=10\n"
        f"- Do not repeat molecules\n\n"
        f"Generate exactly {n} SMILES strings:"
    )

# ── API callers ────────────────────────────────────────────────────────────────
def call_prod(prompt: str) -> tuple[str, float]:
    """OpenAI-compatible format used by dlyog04."""
    t0 = time.time()
    r = requests.post(
        f"{PROD_URL}/v1/chat/completions",
        json={"messages": [{"role": "user", "content": prompt}],
              "max_tokens": 512, "temperature": 0.8},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return text, time.time() - t0


def call_finetune(prompt: str) -> tuple[str, float]:
    """Custom format used by dgx1 fine-tuned server."""
    t0 = time.time()
    r = requests.post(
        f"{FINETUNE_URL}/v1/text",
        json={"prompt": prompt, "max_new_tokens": 512, "temperature": 0.8},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    text = r.json()["response"]
    return text, time.time() - t0


# ── SMILES parsing (same logic as app) ────────────────────────────────────────
_SMILES_RE = re.compile(r"^[A-Za-z0-9@+\-\[\]()=#$/.\\%]+$")

def parse_smiles(text: str) -> list[str]:
    results = []
    for line in text.strip().splitlines():
        line = line.strip().strip(".,;\"'`*")
        line = re.sub(r"^\d+[\.\)]\s*", "", line)   # strip "1. " or "1) "
        line = re.sub(r"\s.*", "", line)             # take first token only
        if line and _SMILES_RE.match(line):
            results.append(line)
    return results


# ── RDKit scoring ──────────────────────────────────────────────────────────────
def score_smiles(smiles_list: list[str], seed_smiles: str) -> dict:
    try:
        from rdkit import Chem, DataStructs
        from rdkit.Chem import Descriptors, QED, AllChem
        try:
            from rdkit.Contrib.SA_Score import sascorer
            has_sas = True
        except Exception:
            has_sas = False
    except ImportError:
        return {"error": "rdkit not installed — run: pip install rdkit"}

    seed_mol = Chem.MolFromSmiles(seed_smiles)
    seed_fp  = AllChem.GetMorganFingerprintAsBitVect(seed_mol, 2, 2048) if seed_mol else None

    valid, qeds, sass, sims = [], [], [], []
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            continue
        valid.append(smi)
        qeds.append(QED.qed(mol))
        if has_sas:
            sass.append(sascorer.calculateScore(mol))
        if seed_fp:
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, 2048)
            sims.append(DataStructs.TanimotoSimilarity(seed_fp, fp))

    n = len(smiles_list)
    return {
        "total_parsed":  n,
        "valid":         len(valid),
        "validity_pct":  round(100 * len(valid) / n, 1) if n else 0,
        "unique_pct":    round(100 * len(set(valid)) / max(len(valid), 1), 1),
        "avg_qed":       round(sum(qeds) / len(qeds), 3) if qeds else 0,
        "avg_sas":       round(sum(sass) / len(sass), 2) if sass else None,
        "avg_tanimoto":  round(sum(sims) / len(sims), 3) if sims else None,
        "valid_smiles":  valid[:5],
    }


# ── Health check ──────────────────────────────────────────────────────────────
def check_health(label: str, base_url: str, path: str = "/health") -> bool:
    try:
        r = requests.get(f"{base_url}{path}", timeout=6)
        data = r.json()
        status = data.get("status", data.get("status", "?"))
        print(f"  [{label}] {base_url} → {status}")
        return r.status_code == 200
    except Exception as e:
        print(f"  [{label}] {base_url} → UNREACHABLE ({e})")
        return False


# ── Main comparison ────────────────────────────────────────────────────────────
def run_comparison(targets: list[dict], n_per_target: int):
    print("\n" + "═"*70)
    print("  MODEL COMPARISON: Production E2B  vs  Fine-tuned E2B")
    print("  Prompt: identical to v2/services/molecule_generator.py")
    print("═"*70)

    all_results = []

    for i, target in enumerate(targets):
        name       = target["name"]
        seed       = target["starter_smiles"]
        aa_seq     = target.get("amino_acid_seq", "")
        known_drug = target.get("known_drug", "")

        print(f"\n{'─'*70}")
        print(f"  TARGET {i+1}: {name}")
        print(f"  Known drug: {known_drug}")
        print(f"  Seed SMILES: {seed[:60]}...")
        print(f"{'─'*70}")

        prompt = build_prompt(seed, aa_seq, noise=0.5, n=n_per_target)

        # Fire both in parallel
        prod_text = ft_text = None
        prod_time = ft_time = 0
        prod_err  = ft_err  = None

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                pool.submit(call_prod,     prompt): "prod",
                pool.submit(call_finetune, prompt): "finetune",
            }
            for future in as_completed(futures):
                label = futures[future]
                try:
                    text, elapsed = future.result()
                    if label == "prod":
                        prod_text, prod_time = text, elapsed
                    else:
                        ft_text, ft_time = text, elapsed
                except Exception as e:
                    if label == "prod":
                        prod_err = str(e)
                    else:
                        ft_err = str(e)

        # Score each
        def score(text, err, label):
            if err:
                print(f"\n  [{label}] ERROR: {err}")
                return None
            smiles = parse_smiles(text)
            sc = score_smiles(smiles, seed)
            return {"raw": text, "smiles": smiles, "scores": sc}

        prod_result = score(prod_text, prod_err, "PROD")
        ft_result   = score(ft_text,   ft_err,   "FINE-TUNED")

        # Print table
        print(f"\n  {'Metric':<25} {'Production E2B':>18} {'Fine-tuned E2B':>18}")
        print(f"  {'─'*25} {'─'*18} {'─'*18}")

        metrics = [
            ("Response time (s)",  f"{prod_time:.1f}" if prod_result else "ERR",
                                    f"{ft_time:.1f}"   if ft_result   else "ERR"),
            ("SMILES parsed",      str(prod_result['scores']['total_parsed']) if prod_result else "ERR",
                                    str(ft_result['scores']['total_parsed'])   if ft_result   else "ERR"),
            ("Valid SMILES %",     str(prod_result['scores']['validity_pct'])  if prod_result else "ERR",
                                    str(ft_result['scores']['validity_pct'])    if ft_result   else "ERR"),
            ("Unique %",           str(prod_result['scores']['unique_pct'])    if prod_result else "ERR",
                                    str(ft_result['scores']['unique_pct'])      if ft_result   else "ERR"),
            ("Avg QED",            str(prod_result['scores']['avg_qed'])       if prod_result else "ERR",
                                    str(ft_result['scores']['avg_qed'])         if ft_result   else "ERR"),
            ("Avg SAS",            str(prod_result['scores']['avg_sas'])       if prod_result else "ERR",
                                    str(ft_result['scores']['avg_sas'])         if ft_result   else "ERR"),
            ("Avg Tanimoto",       str(prod_result['scores']['avg_tanimoto'])  if prod_result else "ERR",
                                    str(ft_result['scores']['avg_tanimoto'])    if ft_result   else "ERR"),
        ]
        for metric, pval, fval in metrics:
            print(f"  {metric:<25} {pval:>18} {fval:>18}")

        if prod_result and prod_result['scores']['valid_smiles']:
            print(f"\n  [PROD]      sample valid SMILES: {prod_result['scores']['valid_smiles'][0]}")
        if ft_result and ft_result['scores']['valid_smiles']:
            print(f"  [FINE-TUNED] sample valid SMILES: {ft_result['scores']['valid_smiles'][0]}")

        all_results.append({
            "target": name,
            "prod":   prod_result,
            "ft":     ft_result,
        })

    # Summary across all targets
    print(f"\n{'═'*70}")
    print("  AGGREGATE SUMMARY")
    print(f"{'═'*70}")

    def avg_metric(key, results_key):
        vals = [r[results_key]['scores'][key] for r in all_results
                if r[results_key] and r[results_key]['scores'].get(key)]
        return round(sum(vals)/len(vals), 3) if vals else "N/A"

    print(f"  {'Metric':<28} {'Production E2B':>16} {'Fine-tuned E2B':>16}")
    print(f"  {'─'*28} {'─'*16} {'─'*16}")
    for metric_key, label in [
        ("validity_pct", "Avg validity %"),
        ("avg_qed",      "Avg QED"),
        ("avg_sas",      "Avg SAS (lower=better)"),
        ("avg_tanimoto", "Avg Tanimoto to seed"),
    ]:
        pv = avg_metric(metric_key, "prod")
        fv = avg_metric(metric_key, "ft")
        print(f"  {label:<28} {str(pv):>16} {str(fv):>16}")

    # Save full results to JSON
    out = Path(__file__).parent / "comparison_results.json"
    with open(out, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Full results saved → {out}")
    print("═"*70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", type=int, default=5,  help="number of targets to test")
    parser.add_argument("--n",       type=int, default=8,  help="SMILES to generate per target")
    args = parser.parse_args()

    # Load targets
    with open(TARGETS_JSON) as f:
        all_targets = json.load(f)

    # Pick a representative spread: beginner + intermediate + advanced
    picks = [t for t in all_targets if t.get("amino_acid_seq") and t.get("starter_smiles")]
    import random; random.seed(42)
    selected = picks[:args.targets]  # first N (sorted by difficulty in file)

    # Health checks
    print("\nChecking API health...")
    prod_ok = check_health("PROD",      PROD_URL,     "/health")
    ft_ok   = check_health("FINE-TUNED", FINETUNE_URL, "/health")

    if not prod_ok and not ft_ok:
        print("Both APIs unreachable — exiting.")
        sys.exit(1)
    if not prod_ok:
        print("WARNING: Production API unreachable — will only show fine-tuned results.")
    if not ft_ok:
        print("WARNING: Fine-tuned API unreachable — will only show production results.")

    run_comparison(selected, args.n)
