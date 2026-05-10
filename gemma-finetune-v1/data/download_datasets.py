"""
Download and filter chemistry datasets + MOSES for SMILES fluency.
Tries multiple sources with fallbacks so it never silently produces 0 records.

Primary:   osunlp/SMolInstruct via HuggingFace Hub Parquet files (bypasses loading script)
Secondary: ChemLLM / Mol-Instructions from HuggingFace (standard Parquet format)
Tertiary:  Synthetic chemistry tasks built from MOSES SMILES + ZINC-like patterns

Usage:
    python3 data/download_datasets.py
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import SMOLINSTRUCT_TASKS, SMOLINSTRUCT_MAX_SAMPLES, MERGED_DATASET_PATH, CUSTOM_DATASET_PATH
from data.dataset_utils import to_gemma4_chatml, save_jsonl, SYSTEM_PROMPT


# ── SMolInstruct via Parquet (bypasses broken loading script) ──────────────────

def _try_smolinstruct_parquet() -> list:
    """
    SMolInstruct stores its data as Parquet files but the repo has a custom
    loading script that newer `datasets` rejects. Bypass it by listing the
    actual Parquet files from the Hub and loading them directly.
    """
    print("  Trying SMolInstruct via direct Parquet download...")
    try:
        from huggingface_hub import list_repo_files
        from datasets import load_dataset

        all_files = list(list_repo_files("osunlp/SMolInstruct", repo_type="dataset"))
        parquet_files = [
            f"https://huggingface.co/datasets/osunlp/SMolInstruct/resolve/main/{f}"
            for f in all_files
            if f.endswith(".parquet") and "train" in f
        ]
        if not parquet_files:
            print("  No train Parquet files found in osunlp/SMolInstruct.")
            return []

        print(f"  Found {len(parquet_files)} Parquet file(s). Loading...")
        ds = load_dataset("parquet", data_files={"train": parquet_files}, split="train")
        print(f"  Loaded {len(ds):,} rows.")
        return ds
    except Exception as e:
        print(f"  SMolInstruct Parquet failed: {e}")
        return []


def _try_mol_instructions() -> list:
    """
    Mol-Instructions is a standard-format chemistry instruction dataset on HuggingFace
    (no custom loading script). Covers molecule generation, description, reactions.
    Ref: https://huggingface.co/datasets/zjunlp/Mol-Instructions
    """
    print("  Trying zjunlp/Mol-Instructions (Parquet-native)...")
    try:
        from datasets import load_dataset
        # Molecule-oriented subset
        ds = load_dataset("zjunlp/Mol-Instructions", "Molecule-oriented Instructions",
                          split="train", trust_remote_code=False)
        print(f"  Loaded {len(ds):,} rows from Mol-Instructions.")
        return ds
    except Exception as e:
        print(f"  Mol-Instructions failed: {e}")
        return []


def _convert_smolinstruct(ds, max_samples: int) -> list:
    """Convert SMolInstruct rows → ChatML records."""
    task_set = set(SMOLINSTRUCT_TASKS)
    filtered = [r for r in ds if r.get("task_type") in task_set]
    print(f"  After task filter: {len(filtered):,}")
    random.seed(42)
    if len(filtered) > max_samples:
        filtered = random.sample(filtered, max_samples)
    records = []
    for r in filtered:
        user = (r.get("input") or r.get("instruction") or "").strip()
        asst = (r.get("output") or r.get("response") or "").strip()
        if user and asst:
            records.append(to_gemma4_chatml(user, asst, system=SYSTEM_PROMPT))
    return records


def _convert_mol_instructions(ds, max_samples: int) -> list:
    """Convert Mol-Instructions rows → ChatML records."""
    random.seed(42)
    sample = list(ds)
    if len(sample) > max_samples:
        sample = random.sample(sample, max_samples)
    records = []
    for r in sample:
        user = (r.get("instruction") or r.get("input") or "").strip()
        asst = (r.get("output") or r.get("response") or "").strip()
        if user and asst:
            records.append(to_gemma4_chatml(user, asst, system=SYSTEM_PROMPT))
    return records


def download_chemistry_instructions() -> list:
    """Try each source in order, return the best result."""
    max_s = SMOLINSTRUCT_MAX_SAMPLES

    # Source 1: SMolInstruct Parquet
    ds = _try_smolinstruct_parquet()
    if ds and len(ds) > 1000:
        records = _convert_smolinstruct(ds, max_s)
        if records:
            print(f"  Using SMolInstruct: {len(records):,} records")
            return records

    # Source 2: Mol-Instructions
    ds = _try_mol_instructions()
    if ds and len(ds) > 1000:
        records = _convert_mol_instructions(ds, max_s)
        if records:
            print(f"  Using Mol-Instructions: {len(records):,} records")
            return records

    # Source 3: Synthetic fallback from MOSES + SMILES patterns
    print("  Both HF datasets unavailable — building synthetic chemistry tasks...")
    return _build_synthetic_chemistry_tasks(max_s // 4)


def _build_synthetic_chemistry_tasks(n: int) -> list:
    """
    Build simple but valid chemistry instruction pairs from SMILES patterns.
    Used as last-resort fallback when HuggingFace is unavailable.
    """
    from data.dataset_utils import is_valid_smiles

    _DRUG_SMILES = [
        ("Aspirin",       "CC(=O)Oc1ccccc1C(=O)O"),
        ("Ibuprofen",     "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O"),
        ("Caffeine",      "Cn1cnc2c1c(=O)n(c(=O)n2C)C"),
        ("Paracetamol",   "CC(=O)Nc1ccc(O)cc1"),
        ("Metformin",     "CN(C)C(=N)NC(=N)N"),
        ("Oseltamivir",   "CCOC(=O)[C@@H]1CC(=C[C@@H](O1)OC(CC)CC)NC(C)=O"),
        ("Nirmatrelvir",  "CC1(C2CC2NC(=O)C(F)(F)F)C(=O)N[C@@H](Cc2ccc(C#N)cc2)C1=O"),
        ("Imatinib",      "Cc1ccc(cc1Nc2nccc(n2)c3cccnc3)NC(=O)c4ccc(cc4)CN5CCN(CC5)C"),
        ("Erlotinib",     "C#Cc1cccc(c1)Nc2ncnc3cc(OCC)c(OCC)cc23"),
        ("Gefitinib",     "COc1cc2ncnc(Nc3cccc(Cl)c3F)c2cc1OCCCN4CCOCC4"),
    ]

    tasks = [
        "Generate 5 novel drug-like SMILES inspired by {name} ({smiles}). MW 200-500, QED>0.4.",
        "Generate 3 analogues of {name} ({smiles}) with improved water solubility.",
        "Starting from {name} ({smiles}), generate 4 SMILES with lower MW (< 400) and higher QED.",
        "Generate 5 drug-like molecules in the same chemical class as {name}.",
    ]

    records = []
    random.seed(42)
    while len(records) < n:
        name, smiles = random.choice(_DRUG_SMILES)
        task_tmpl = random.choice(tasks)
        user = task_tmpl.format(name=name, smiles=smiles)
        # Synthetic response — just enough structure for the model to learn format
        asst = "\n".join([
            f"{i+1}. {smiles}{random.choice(['O','N','C','F','Cl','CC','C(=O)N'])}  # synthetic variant {i+1}"
            for i in range(4)
        ])
        records.append(to_gemma4_chatml(user, asst, system=SYSTEM_PROMPT))

    print(f"  Built {len(records):,} synthetic chemistry tasks (fallback).")
    return records[:n]


# ── MOSES SMILES fluency ───────────────────────────────────────────────────────

def download_moses_smiles(n: int = 20_000) -> list:
    print(f"Loading MOSES ({n:,} SMILES)...")
    try:
        from datasets import load_dataset
        ds = load_dataset("katielink/moses", split="train", trust_remote_code=False)
        ds = list(ds)
        random.seed(42)
        if len(ds) > n:
            ds = random.sample(ds, n)
        records = []
        for row in ds:
            smiles = (row.get("smiles") or row.get("SMILES") or "").strip()
            if smiles:
                records.append(to_gemma4_chatml(
                    "Generate a drug-like molecule SMILES string.", smiles))
        print(f"  MOSES records: {len(records):,}")
        return records
    except Exception as e:
        print(f"  MOSES failed: {e}")
        return []


# ── Custom dataset append ──────────────────────────────────────────────────────

def load_custom_dataset() -> list:
    if os.path.exists(CUSTOM_DATASET_PATH):
        from data.dataset_utils import load_jsonl
        records = load_jsonl(CUSTOM_DATASET_PATH)
        print(f"  Custom dataset: {len(records):,} records from {CUSTOM_DATASET_PATH}")
        return records
    print(f"  Custom dataset not found at {CUSTOM_DATASET_PATH} — run build_custom_dataset.py first.")
    return []


# ── Main ───────────────────────────────────────────────────────────────────────

def merge_and_save(chemistry: list, moses: list, custom: list):
    all_records = chemistry + moses + custom
    random.seed(42)
    random.shuffle(all_records)
    os.makedirs(os.path.dirname(MERGED_DATASET_PATH) or ".", exist_ok=True)
    save_jsonl(all_records, MERGED_DATASET_PATH)
    print(f"\n{'='*50}")
    print(f"MERGED DATASET SUMMARY:")
    print(f"  Chemistry instructions: {len(chemistry):,}")
    print(f"  MOSES SMILES fluency:   {len(moses):,}")
    print(f"  Deep2Lead custom:       {len(custom):,}")
    print(f"  TOTAL:                  {len(all_records):,}")
    print(f"  Saved → {MERGED_DATASET_PATH}")
    print(f"{'='*50}")


if __name__ == "__main__":
    print("="*50)
    print("[1/3] Chemistry instruction dataset")
    chem_records   = download_chemistry_instructions()

    print("\n[2/3] MOSES SMILES fluency dataset")
    moses_records  = download_moses_smiles(20_000)

    print("\n[3/3] Deep2Lead custom dataset")
    custom_records = load_custom_dataset()

    merge_and_save(chem_records, moses_records, custom_records)
    print("\nDone. Run train/finetune_gemma4.py next.")
