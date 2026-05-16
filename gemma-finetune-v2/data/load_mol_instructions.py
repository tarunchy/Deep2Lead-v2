"""
Load Mol-Instructions from local git clone (bypasses HuggingFace script restriction).

Clone first:
  git clone https://huggingface.co/datasets/zjunlp/Mol-Instructions \
            /home/dlyog/data/mol-instructions

Loads parquet files directly — no dataset scripts needed.

Usage:
  python3 data/load_mol_instructions.py \
      --local-dir /home/dlyog/data/mol-instructions \
      --output ./data/mol_instructions.jsonl \
      --max 25000
"""

import argparse
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _iter_parquet(local_dir: str):
    """Yield rows from all parquet files under local_dir."""
    try:
        import pandas as pd
    except ImportError:
        log.error("pandas not installed — run: pip install pandas pyarrow")
        return

    parquet_files = sorted(Path(local_dir).rglob("*.parquet"))
    log.info(f"Found {len(parquet_files)} parquet files in {local_dir}")

    for pf in parquet_files:
        try:
            df = pd.read_parquet(pf)
            for _, row in df.iterrows():
                yield dict(row)
        except Exception as e:
            log.warning(f"  Skipping {pf}: {e}")


def load_mol_instructions(local_dir: str, output_path: str, max_records: int) -> int:
    from data.dataset_utils import to_gemma4_chatml, SYSTEM_PROMPT

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not os.path.exists(local_dir):
        log.error(f"Local dir not found: {local_dir}")
        log.error("Run: git clone https://huggingface.co/datasets/zjunlp/Mol-Instructions "
                  f"{local_dir}")
        return 0

    written = 0
    skipped = 0

    with open(out, "w") as f:
        for row in _iter_parquet(local_dir):
            if written >= max_records:
                break

            user = (row.get("instruction") or row.get("input") or "").strip()
            asst = (row.get("output") or row.get("response") or "").strip()

            if not user or not asst or len(user) < 10 or len(asst) < 10:
                skipped += 1
                continue

            record = to_gemma4_chatml(user, asst, system=SYSTEM_PROMPT)
            f.write(json.dumps(record) + "\n")
            written += 1

    log.info(f"Mol-Instructions: wrote {written:,} records (skipped {skipped:,})")
    return written


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    parser = argparse.ArgumentParser()
    parser.add_argument("--local-dir", default="/home/dlyog/data/mol-instructions")
    parser.add_argument("--output",    default="./data/mol_instructions.jsonl")
    parser.add_argument("--max",       type=int, default=25_000)
    args = parser.parse_args()

    n = load_mol_instructions(args.local_dir, args.output, args.max)
    print(f"Written {n:,} records → {args.output}")
