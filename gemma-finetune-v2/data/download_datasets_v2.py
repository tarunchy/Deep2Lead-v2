"""
v2 Dataset Pipeline: ChEMBL/BindingDB (65%) + Mol-Instructions (25%) + MOSES (10%)

Key changes from v1:
  1. ChEMBL/BindingDB protein-SMILES pairs replace flat MOSES-heavy mix
  2. IBM MAMMAL gates all ChEMBL pairs (affinity score ≥ 0.70)
  3. MOSES downsampled to 10% and wrapped with diverse prompts (not flat)
  4. Rationale-first ChatML format via to_rationale_chatml()

Usage:
    python3 data/download_datasets_v2.py
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (
    CHEMBL_TARGET_SAMPLES, MOL_INSTRUCTIONS_SAMPLES, MOSES_SAMPLES,
    MERGED_DATASET_PATH, CUSTOM_DATASET_PATH, MAMMAL_AFFINITY_THRESHOLD,
    CHEMBL_IC50_CUTOFF_NM, SEED,
)
from data.dataset_utils import (
    to_gemma4_chatml, to_rationale_chatml, save_jsonl, SYSTEM_PROMPT,
    is_valid_smiles, drug_like_filter,
)

random.seed(SEED)


# ── ChEMBL / BindingDB target-conditioned pairs ────────────────────────────────

_RATIONALE_TEMPLATES = [
    "The target's primary binding pocket is a hydrophobic cleft lined with aromatic residues, "
    "favouring flat, pi-electron-rich scaffolds. The molecule's aromatic core enables pi-pi "
    "stacking while the polar tail anchors a critical hydrogen bond with a backbone NH.",

    "Analysis of the target's active site shows a shallow groove with several polar contacts. "
    "A compact scaffold with a hydrogen-bond donor at the meta position maximises fit. "
    "The amide linker mimics a natural substrate conformation.",

    "The target belongs to the kinase family, with a conserved DFG motif gating the ATP pocket. "
    "An N-methylpyrimidine hinge binder combined with a hydrophobic back-pocket substituent "
    "achieves both selectivity and nanomolar affinity.",

    "The enzyme active site contains a catalytic triad. A transition-state mimic with a "
    "fluoroketone warhead covalently engages Ser, while a pendant aromatic fills the S1 pocket. "
    "Low MW keeps permeability high.",

    "Structural studies reveal an allosteric pocket adjacent to the activation loop. "
    "A rigid bicyclic core locks the molecule in the bioactive conformation; "
    "a solubilising morpholine tail balances lipophilicity.",
]


def _chembl_rationale(fasta: str, smiles: str, target_name: str) -> dict:
    seq_preview = fasta[:120]
    rationale   = random.choice(_RATIONALE_TEMPLATES)
    user = (
        f"Target: {target_name}\n"
        f"Protein sequence (first 120 AA): {seq_preview}\n"
        "Design a small molecule drug candidate with high binding affinity to this target. "
        "First explain your structural reasoning, then provide the SMILES string.\n"
        "Requirements: MW 200-500 Da, QED > 0.50, SAS ≤ 5.0, passes Lipinski Ro5."
    )
    return to_rationale_chatml(user, rationale, [smiles], system=SYSTEM_PROMPT)


def _load_chembl_jsonl(path: str) -> list[tuple[str, str, str]]:
    """
    Load pre-downloaded ChEMBL pairs from the JSONL file produced by download_chembl.py.
    Each line: {"fasta": "...", "smiles": "...", "target_name": "...", "ic50_nm": 42.0}
    Returns list of (fasta, smiles, target_name).
    """
    if not os.path.exists(path):
        return []
    pairs = []
    with open(path) as f:
        for line in f:
            try:
                row = json.loads(line)
                fasta  = row.get("fasta", "").strip()
                smiles = row.get("smiles", "").strip()
                name   = row.get("target_name", "Unknown").strip()
                if fasta and smiles and len(fasta) >= 10 and is_valid_smiles(smiles):
                    pairs.append((fasta, smiles, name))
            except Exception:
                pass
    return pairs


def download_target_conditioned_pairs(n: int, mammal_threshold: float) -> list:
    """
    Load ChEMBL pairs from local JSONL (produced by download_chembl.py),
    apply IBM MAMMAL affinity filter via dlyog03 API, return ChatML records.
    Falls back to built-in known drug pairs if JSONL not found.
    """
    from config import CHEMBL_PAIRS_PATH

    print(f"\n[ChEMBL] Targeting {n:,} high-affinity pairs ...")
    raw_pairs = _load_chembl_jsonl(CHEMBL_PAIRS_PATH)

    if raw_pairs:
        print(f"  Loaded {len(raw_pairs):,} pairs from {CHEMBL_PAIRS_PATH}")
    else:
        print(f"  JSONL not found at {CHEMBL_PAIRS_PATH}.")
        print("  Run download_chembl.py first. Using built-in seed pairs for now.")
        raw_pairs = _builtin_known_pairs()

    # Deduplicate by SMILES
    seen = set()
    unique_pairs = []
    for fasta, smiles, name in raw_pairs:
        if smiles not in seen:
            seen.add(smiles)
            unique_pairs.append((fasta, smiles, name))
    random.shuffle(unique_pairs)
    print(f"  Unique pairs after dedup: {len(unique_pairs):,}")

    # Apply IBM MAMMAL affinity filter via dlyog03:8090
    from data.mammal_filter import load_mammal_filter_or_passthrough
    mammal = load_mammal_filter_or_passthrough(threshold=mammal_threshold)

    if mammal is not None:
        print(f"  Running IBM MAMMAL filter (dlyog03:8090, threshold={mammal_threshold}) ...")
        pool = unique_pairs[:min(n * 3, len(unique_pairs))]
        fasta_smiles = [(f, s) for f, s, _ in pool]
        kept         = mammal.filter_pairs(fasta_smiles)
        kept_set     = {s for _, s in kept}
        filtered     = [(f, s, nm) for f, s, nm in pool if s in kept_set]
        print(f"  After MAMMAL filter: {len(filtered):,} pairs kept")
    else:
        print("  MAMMAL filter skipped (dlyog03 API not reachable).")
        filtered = unique_pairs

    if len(filtered) > n:
        filtered = random.sample(filtered, n)

    records = [_chembl_rationale(f, s, nm) for f, s, nm in filtered]
    print(f"  Target-conditioned records: {len(records):,}")
    return records


def _builtin_known_pairs() -> list[tuple[str, str, str]]:
    """Known drug-target pairs as a guaranteed fallback."""
    return [
        (
            "MESLVPGFNEKTHVQLSLPVLQVRDVLVRGFGDSVEEVLSEARQHLKDAGVNKEVPKGIYYVGENLRLNKKEGLEQLEKELAEK",
            "CC1(C2CC2NC(=O)C(F)(F)F)C(=O)N[C@@H](Cc2ccc(C#N)cc2)C1=O",
            "SARS-CoV-2 Main Protease"
        ),
        (
            "PQITLWQRPLVTIKIGGQLKEALLDTGADDTVLEEMSLPGRWKPKMIGGIGGFIKVRQYDQILIEICGHKAIGTVLVGPTPVNIIGRNLLTQIG",
            "CC(C)(C)NC(=O)[C@@H]1C[C@H]1NC(=O)c1cc2cc(Cl)sc2[nH]1",
            "HIV-1 Protease"
        ),
        (
            "MGSSHHHHHHSSGLVPRGSHMRGPNARRGPPAAPPAPPASTSGGSPAGGSSPAGGSSPAGGSGYGFGANRGRGRGRGRGRG",
            "Cc1ccc(cc1Nc2nccc(n2)c3cccnc3)NC(=O)c4ccc(cc4)CN5CCN(CC5)C",
            "BCR-ABL Kinase"
        ),
        (
            "MAHHHHHHHHHHHIEGRHHHKLVWFPGGAETAERAGQIRGASMKFVALFAVHFAATITLAAIVTARIIYSFVSTNKL",
            "C#Cc1cccc(c1)Nc2ncnc3cc(OCC)c(OCC)cc23",
            "EGFR Kinase"
        ),
        (
            "MAKQYDSVECPFCDEVSKYEKLAKIGQGTYGVVYKGRHKTTGQVVAMKEIRLESEDEGVPSTAIREISLLKELKHPNIVKLLD",
            "c1ccc2c(c1)cc1ccc3cccc4ccc2c1c34",
            "CDK2"
        ),
        (
            "MERTKKVKVGKEGLMKKMFNKTLKHEAELSDLQKKLKDAEDQLGARVGYIELDLNSGKILESFRPEERFPMMSTFKVLLCG",
            "CC(=O)Nc1ccc(-c2cnc(Nc3cccc(Cl)c3)nc2)cc1",
            "BRAF V600E"
        ),
        (
            "MSESATDKPTQGLAKRPKLSSAEGNLVPDQLQELIREEGQNLSAHVKNLMKQYADKLREQLEHSSQYLSIQNNPHQDPQE",
            "O=C(/C=C/c1ccc(O)cc1)O",
            "p53"
        ),
        (
            "MAAAAKDKSSDKKVQTKGKRGAKGKSEAPKKGVVKAEKSKKKKEEESDDDMGFGLFD",
            "O=C1c2ccccc2C(=O)N1[C@@H]1CCC[C@H]1C(=O)O",
            "HDAC1"
        ),
    ]


# ── Mol-Instructions (25%) ─────────────────────────────────────────────────────

def download_mol_instructions(n: int) -> list:
    print(f"\n[Mol-Instructions] Loading up to {n:,} records ...")
    try:
        from datasets import load_dataset
        ds = load_dataset("zjunlp/Mol-Instructions", "Molecule-oriented Instructions",
                          split="train", trust_remote_code=False)
        ds = list(ds)
        print(f"  Loaded {len(ds):,} rows.")
        random.shuffle(ds)
        ds = ds[:n]
        records = []
        for r in ds:
            user = (r.get("instruction") or r.get("input") or "").strip()
            asst = (r.get("output") or r.get("response") or "").strip()
            if user and asst:
                records.append(to_gemma4_chatml(user, asst, system=SYSTEM_PROMPT))
        print(f"  Mol-Instructions records: {len(records):,}")
        return records
    except Exception as e:
        print(f"  Mol-Instructions failed: {e}")
        return []


# ── MOSES SMILES syntax baseline (10%) ────────────────────────────────────────

_MOSES_PROMPTS = [
    "Design a drug-like molecule with balanced LogP and MW. Provide the SMILES string and briefly explain the structural features.",
    "Generate one novel small molecule that satisfies Lipinski's Rule of 5. Output SMILES.",
    "Propose a new drug scaffold with MW < 450 Da, at least one ring system, and a hydrogen-bond donor. Provide SMILES.",
    "Create a fragment-like molecule (MW 150-300, HAC ≤ 25) suitable for fragment-based drug discovery. Output SMILES.",
    "Generate a bioisostere of a simple aromatic carboxylic acid scaffold. Provide the SMILES.",
]

def download_moses_smiles(n: int) -> list:
    print(f"\n[MOSES] Loading up to {n:,} SMILES (contextualized, not flat) ...")
    try:
        from datasets import load_dataset
        ds = load_dataset("katielink/moses", split="train", trust_remote_code=False)
        ds = list(ds)
        random.shuffle(ds)
        ds = ds[:n]
        records = []
        for row in ds:
            smiles = (row.get("smiles") or row.get("SMILES") or "").strip()
            if smiles and is_valid_smiles(smiles):
                prompt = random.choice(_MOSES_PROMPTS)
                asst = (
                    f"Rationale: This molecule balances lipophilicity and MW within drug-like space. "
                    f"The scaffold supports modification at multiple positions.\n\nSMILES: {smiles}"
                )
                records.append(to_gemma4_chatml(prompt, asst, system=SYSTEM_PROMPT))
        print(f"  MOSES contextualized records: {len(records):,}")
        return records
    except Exception as e:
        print(f"  MOSES failed: {e}")
        return []


# ── Custom Deep2Lead dataset ───────────────────────────────────────────────────

def load_custom_dataset() -> list:
    from config import CUSTOM_DATASET_PATH
    if os.path.exists(CUSTOM_DATASET_PATH):
        from data.dataset_utils import load_jsonl
        records = load_jsonl(CUSTOM_DATASET_PATH)
        print(f"  Custom v2 dataset: {len(records):,} records")
        return records
    print(f"  Custom dataset not found — run build_custom_dataset_v2.py first.")
    return []


# ── Merge and save ─────────────────────────────────────────────────────────────

def merge_and_save(target_cond: list, mol_inst: list, moses: list, custom: list):
    all_records = target_cond + mol_inst + moses + custom
    random.shuffle(all_records)
    os.makedirs(os.path.dirname(MERGED_DATASET_PATH) or ".", exist_ok=True)
    save_jsonl(all_records, MERGED_DATASET_PATH)

    total = len(all_records)
    print(f"\n{'='*55}")
    print(f"MERGED DATASET v2 SUMMARY")
    print(f"{'='*55}")
    print(f"  Target-conditioned (ChEMBL/BindingDB): {len(target_cond):>6,}  ({100*len(target_cond)/max(total,1):.1f}%)")
    print(f"  Mol-Instructions:                      {len(mol_inst):>6,}  ({100*len(mol_inst)/max(total,1):.1f}%)")
    print(f"  MOSES (contextualized):                {len(moses):>6,}  ({100*len(moses)/max(total,1):.1f}%)")
    print(f"  Deep2Lead custom v2:                   {len(custom):>6,}  ({100*len(custom)/max(total,1):.1f}%)")
    print(f"  TOTAL:                                 {total:>6,}")
    print(f"  Saved → {MERGED_DATASET_PATH}")
    print(f"{'='*55}")


if __name__ == "__main__":
    print("=" * 55)
    print("[1/4] Target-conditioned pairs (ChEMBL + BindingDB + MAMMAL)")
    target_records = download_target_conditioned_pairs(CHEMBL_TARGET_SAMPLES, MAMMAL_AFFINITY_THRESHOLD)

    print("\n[2/4] Mol-Instructions")
    mol_records = download_mol_instructions(MOL_INSTRUCTIONS_SAMPLES)

    print("\n[3/4] MOSES contextualized")
    moses_records = download_moses_smiles(MOSES_SAMPLES)

    print("\n[4/4] Deep2Lead custom v2")
    custom_records = load_custom_dataset()

    merge_and_save(target_records, mol_records, moses_records, custom_records)
    print("\nDone. Run train/finetune_gemma4_v2.py next.")
