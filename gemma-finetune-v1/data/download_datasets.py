"""
Download and filter SMolInstruct (primary dataset) + MOSES (SMILES fluency).
Run once on DGX before training.

Usage:
    python3 data/download_datasets.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import SMOLINSTRUCT_TASKS, SMOLINSTRUCT_MAX_SAMPLES, MERGED_DATASET_PATH
from data.dataset_utils import to_gemma4_chatml, save_jsonl, SYSTEM_PROMPT


def download_smolinstruct() -> list:
    """
    Download osunlp/SMolInstruct, filter to chemistry generation tasks,
    and convert to Gemma4 ChatML format.
    """
    print("Loading SMolInstruct from HuggingFace (may take a few minutes)...")
    from datasets import load_dataset

    ds = load_dataset("osunlp/SMolInstruct", split="train", trust_remote_code=True)
    print(f"  Total records: {len(ds):,}")

    filtered = ds.filter(
        lambda x: x.get("task_type") in SMOLINSTRUCT_TASKS,
        num_proc=4,
    )
    print(f"  After task filter: {len(filtered):,}")

    # Trim to budget
    if len(filtered) > SMOLINSTRUCT_MAX_SAMPLES:
        filtered = filtered.shuffle(seed=42).select(range(SMOLINSTRUCT_MAX_SAMPLES))
    print(f"  Using: {len(filtered):,} samples")

    records = []
    for sample in filtered:
        user_text = sample.get("input", "").strip()
        asst_text = sample.get("output", "").strip()
        if not user_text or not asst_text:
            continue
        records.append(to_gemma4_chatml(user_text, asst_text, system=SYSTEM_PROMPT))

    print(f"  Converted: {len(records):,} ChatML records")
    return records


def download_moses_smiles(n: int = 20_000) -> list:
    """
    Download MOSES drug-like SMILES and build simple completion tasks.
    Teaches basic SMILES grammar / fluency.
    """
    print(f"Loading MOSES ({n:,} SMILES)...")
    from datasets import load_dataset

    try:
        ds = load_dataset("katielink/moses", split="train", trust_remote_code=True)
    except Exception as e:
        print(f"  MOSES load failed ({e}), skipping.")
        return []

    ds = ds.shuffle(seed=42).select(range(min(n, len(ds))))

    records = []
    for sample in ds:
        smiles = sample.get("smiles", "").strip()
        if not smiles:
            continue
        user_text = "Generate a drug-like molecule SMILES string."
        asst_text = smiles
        records.append(to_gemma4_chatml(user_text, asst_text))

    print(f"  MOSES records: {len(records):,}")
    return records


def merge_and_save(smolinstruct: list, moses: list):
    import random
    all_records = smolinstruct + moses
    random.seed(42)
    random.shuffle(all_records)
    os.makedirs(os.path.dirname(MERGED_DATASET_PATH) or ".", exist_ok=True)
    save_jsonl(all_records, MERGED_DATASET_PATH)
    print(f"\nTotal training records: {len(all_records):,} → {MERGED_DATASET_PATH}")


if __name__ == "__main__":
    smolinstruct_records = download_smolinstruct()
    moses_records        = download_moses_smiles(20_000)
    merge_and_save(smolinstruct_records, moses_records)
    print("\nDone. Run train/finetune_gemma4.py next.")
