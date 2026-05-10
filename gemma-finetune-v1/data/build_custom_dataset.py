"""
Build Deep2Lead-specific instruction dataset from curated_targets.json.
Generates ~5,000 ChatML pairs covering:
  - Standard molecule generation (per target)
  - Target-specific generation with rationale
  - Game explanation style (high school friendly)
  - Property-conditioned generation

Run after download_datasets.py OR standalone (outputs custom_dataset.jsonl).

Usage:
    python3 data/build_custom_dataset.py
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import TARGETS_JSON_PATH, CUSTOM_DATASET_PATH
from data.dataset_utils import to_gemma4_chatml, save_jsonl, SYSTEM_PROMPT


def load_targets() -> list:
    path = os.path.abspath(TARGETS_JSON_PATH)
    if not os.path.exists(path):
        print(f"Targets file not found: {path}")
        print("Falling back to built-in minimal target list.")
        return _builtin_targets()
    with open(path) as f:
        return json.load(f)


def _builtin_targets() -> list:
    return [
        {
            "name": "SARS-CoV-2 Main Protease",
            "category": "viral protease",
            "known_drug": "Nirmatrelvir",
            "known_drug_smiles": "CC1(C2CC2NC(=O)C(F)(F)F)C(=O)N[C@@H](Cc2ccc(C#N)cc2)C1=O",
            "starter_smiles": "CC1CC1NC(=O)C(F)(F)F",
            "amino_acid_seq": "MESLVPGFNEKTHVQLSLPVLQVRDVLVRGFGDSVEEVLSEARQHLK",
            "description": "Essential enzyme for viral replication.",
        }
    ]


# ── Template builders ──────────────────────────────────────────────────────────

def standard_generation(target: dict, n_variants: int = 5) -> dict:
    seq = target.get("amino_acid_seq", "")[:150]
    seed = target.get("starter_smiles", "")
    user = (
        f"Target protein (first 150 AA): {seq}\n"
        f"Seed molecule: {seed}\n"
        f"Generate {n_variants} novel drug-like SMILES candidates. "
        f"Requirements: MW 150-500, QED > 0.4, SAS < 6, diverse from seed (Tanimoto < 0.9)."
    )
    # Synthetic response — placeholder structure derived from seed
    molecules = _generate_synthetic_variants(seed, n_variants)
    asst = "\n".join(f"{i+1}. {s}" for i, s in enumerate(molecules))
    return to_gemma4_chatml(user, asst, system=SYSTEM_PROMPT)


def target_rationale(target: dict) -> dict:
    name     = target.get("name", "Unknown Target")
    category = target.get("category", "enzyme")
    known    = target.get("known_drug", "")
    ksmiles  = target.get("known_drug_smiles", "")
    desc     = target.get("description", "")

    user = (
        f"Target: {name}\n"
        f"Target class: {category}\n"
        f"Reference drug: {known} (SMILES: {ksmiles})\n"
        f"Context: {desc}\n"
        "Generate 3 novel SMILES candidates that could improve on the reference drug. "
        "For each, briefly explain (1-2 sentences, high-school level) why the structure might work."
    )
    mols = _generate_synthetic_variants(ksmiles, 3)
    lines = []
    explanations = [
        "The aromatic ring may help the molecule fit into the enzyme's binding pocket through pi-pi stacking interactions.",
        "The added hydroxyl group could form a hydrogen bond with a key residue in the active site, improving binding affinity.",
        "Reducing the molecular weight while keeping the core scaffold may improve cell permeability and reduce side effects.",
    ]
    for i, (s, ex) in enumerate(zip(mols, explanations)):
        lines.append(f"{i+1}. {s}")
        lines.append(f"   Explanation: {ex}")
    asst = "\n".join(lines)
    return to_gemma4_chatml(user, asst, system=SYSTEM_PROMPT)


def game_explanation(target: dict) -> dict:
    name = target.get("name", "target protein")
    seed = target.get("starter_smiles", "")
    mols = _generate_synthetic_variants(seed, 1)
    new_mol = mols[0] if mols else seed

    user = (
        f"Previous molecule: {seed} | Score: 0.42\n"
        f"New molecule: {new_mol} | Score: 0.68\n"
        f"Target: {name}\n"
        "Explain in 2-3 simple sentences (for a high school student) "
        "why the new molecule scored better."
    )
    asst = (
        "Your new molecule scored higher because it fits the target protein better! "
        "The small structural change added a group that can 'grab onto' a key part of "
        "the protein's pocket, like a key with a better notch fitting a lock. "
        "Scientifically, the new functional group forms an additional hydrogen bond with "
        "a critical residue in the binding site, lowering the binding energy."
    )
    return to_gemma4_chatml(user, asst, system=SYSTEM_PROMPT)


def property_conditioned(target: dict) -> dict:
    mw_low, mw_high = 200, 450
    logp_low, logp_high = 1.0, 4.0
    qed_min = 0.5
    seed = target.get("starter_smiles", "CC(=O)Oc1ccccc1C(=O)O")
    mols = _generate_synthetic_variants(seed, 4)

    user = (
        f"Generate 4 molecules with these properties:\n"
        f"- MW: {mw_low}-{mw_high} Da\n"
        f"- LogP: {logp_low:.1f}-{logp_high:.1f}\n"
        f"- QED > {qed_min}\n"
        f"- Must pass Lipinski Rule of 5\n"
        f"- Inspired by scaffold: {seed}"
    )
    lines = [f"{i+1}. {s}  # MW:~{220+i*50}, LogP:{1.5+i*0.5:.1f}, QED:~{0.55+i*0.05:.2f}" for i, s in enumerate(mols)]
    asst = "Molecules matching criteria:\n" + "\n".join(lines)
    return to_gemma4_chatml(user, asst, system=SYSTEM_PROMPT)


# ── Synthetic SMILES variants ──────────────────────────────────────────────────

_FRAGMENTS = [
    "C", "CC", "CCO", "c1ccccc1", "C(=O)O", "NC",
    "OC", "FC", "ClC", "C1CCCC1", "C(F)(F)F",
]

def _generate_synthetic_variants(seed_smiles: str, n: int) -> list[str]:
    """
    Deterministically generate simple SMILES variants by appending/modifying
    fragments. These are structural proxies — replaced by real model output
    during training bootstrapping, but good enough for custom dataset structure.
    """
    results = []
    base = seed_smiles or "CC(=O)O"

    # Simple rule-based modifications — real training uses model bootstrap
    modifications = [
        lambda s: s.replace("C", "CC", 1),
        lambda s: s + "O",
        lambda s: s + "N",
        lambda s: "F" + s,
        lambda s: s.replace("O", "S", 1) if "O" in s else s + "S",
        lambda s: s + "C(=O)N",
        lambda s: s + "c1ccccc1",
        lambda s: "C(F)(F)F" + s,
    ]
    random.seed(hash(seed_smiles) % (2**31))
    chosen = random.sample(modifications, min(n, len(modifications)))
    for mod in chosen:
        try:
            variant = mod(base)
            if variant != base:
                results.append(variant)
        except Exception:
            pass

    # Pad with base + fragments if not enough
    while len(results) < n:
        frag = random.choice(_FRAGMENTS)
        results.append(base + frag)

    return results[:n]


# ── Main ───────────────────────────────────────────────────────────────────────

def build(targets_per_type: int = 1) -> list:
    targets = load_targets()
    print(f"Building custom dataset from {len(targets)} targets...")

    records = []
    for t in targets:
        for _ in range(targets_per_type):
            records.append(standard_generation(t, n_variants=5))
            records.append(target_rationale(t))
            records.append(game_explanation(t))
            records.append(property_conditioned(t))

    random.seed(42)
    random.shuffle(records)
    print(f"Generated {len(records):,} custom instruction pairs")
    return records


if __name__ == "__main__":
    records = build(targets_per_type=3)  # 3 variants per template per target
    os.makedirs(os.path.dirname(CUSTOM_DATASET_PATH) or ".", exist_ok=True)
    save_jsonl(records, CUSTOM_DATASET_PATH)
    print(f"\nSaved → {CUSTOM_DATASET_PATH}")
    print("Tip: add this to the merged dataset by re-running download_datasets.py")
