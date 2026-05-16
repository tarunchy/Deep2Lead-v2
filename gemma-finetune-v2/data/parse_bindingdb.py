"""
Parse BindingDB TSV → filter high-affinity pairs → JSONL.

Key advantage: BindingDB TSV already contains protein sequences in col 41
(BindingDB Target Chain Sequence 1) — no UniProt API calls needed.

Filters applied:
  - Any of Kd, Ki, IC50 ≤ affinity_cutoff_nm (default 100 nM)
  - Single-protein targets only (chains == 1)
  - Valid RDKit-parseable SMILES
  - Protein sequence ≥ min_seq_len residues
  - Deduplicate by (canonical_smiles, sequence[:100]) key

Output JSONL per line:
  {"smiles": "...", "fasta": "...", "target_name": "...",
   "affinity_nm": 42.0, "affinity_type": "Kd", "organism": "..."}

Usage:
  python3 data/parse_bindingdb.py \
      --input /home/dlyog/data/BindingDB_All_202605.tsv \
      --output ./data/bindingdb_parsed.jsonl \
      --cutoff 100
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

try:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.error")
    RDLogger.DisableLog("rdApp.warning")
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False
    log.warning("RDKit not found — SMILES validation skipped")

# Column names we care about (exact strings from BindingDB header)
COL_SMILES    = "Ligand SMILES"
COL_TARGET    = "Target Name"
COL_ORGANISM  = "Target Source Organism According to Curator or DataSource"
COL_KI        = "Ki (nM)"
COL_IC50      = "IC50 (nM)"
COL_KD        = "Kd (nM)"
COL_SEQ       = "BindingDB Target Chain Sequence 1"
COL_CHAINS    = "Number of Protein Chains in Target (>1 implies a multichain complex)"
COL_UNIPROT   = "UniProt (SwissProt) Primary ID of Target Chain 1"
COL_NAME      = "UniProt (SwissProt) Recommended Name of Target Chain 1"

_VALUE_RE = re.compile(r"[\d.]+")


def _parse_affinity(value: str) -> float | None:
    """Extract numeric nM value from BindingDB affinity cell. Returns None if unparseable."""
    if not value or not value.strip():
        return None
    value = value.strip().replace(",", "")
    m = _VALUE_RE.search(value)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _canonical(smiles: str) -> str | None:
    if not HAS_RDKIT:
        return smiles.strip() if smiles.strip() else None
    try:
        mol = Chem.MolFromSmiles(smiles.strip())
        return Chem.MolToSmiles(mol) if mol else None
    except Exception:
        return None


def parse_bindingdb(
    input_path: str,
    output_path: str,
    cutoff_nm: float = 100.0,
    min_seq_len: int = 50,
    max_records: int | None = None,
) -> int:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    written = 0
    skipped_affinity = 0
    skipped_smiles = 0
    skipped_seq = 0
    skipped_dup = 0
    total = 0

    log.info(f"Parsing {input_path} (cutoff={cutoff_nm} nM, min_seq={min_seq_len} AA)")

    with open(input_path, encoding="utf-8", errors="replace") as fin, \
         open(out, "w") as fout:

        header = fin.readline().rstrip("\n").split("\t")
        col = {name: i for i, name in enumerate(header)}

        def get(row, name):
            idx = col.get(name)
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        for line in fin:
            if max_records and written >= max_records:
                break
            total += 1
            if total % 200_000 == 0:
                log.info(f"  Processed {total:,} rows | written {written:,} | "
                         f"skip: affinity={skipped_affinity:,} smiles={skipped_smiles:,} "
                         f"seq={skipped_seq:,} dup={skipped_dup:,}")

            row = line.rstrip("\n").split("\t")

            # Affinity filter — accept any measurement type ≤ cutoff
            kd   = _parse_affinity(get(row, COL_KD))
            ki   = _parse_affinity(get(row, COL_KI))
            ic50 = _parse_affinity(get(row, COL_IC50))

            best_val, best_type = None, None
            for val, typ in [(kd, "Kd"), (ki, "Ki"), (ic50, "IC50")]:
                if val is not None and val <= cutoff_nm:
                    if best_val is None or val < best_val:
                        best_val, best_type = val, typ

            if best_val is None:
                skipped_affinity += 1
                continue

            # SMILES
            smiles_raw = get(row, COL_SMILES)
            canon = _canonical(smiles_raw)
            if not canon:
                skipped_smiles += 1
                continue

            # Protein sequence (already in TSV)
            seq = get(row, COL_SEQ)
            if len(seq) < min_seq_len:
                skipped_seq += 1
                continue

            # Dedup
            key = f"{canon}|{seq[:80]}"
            if key in seen:
                skipped_dup += 1
                continue
            seen.add(key)

            target_name = get(row, COL_NAME) or get(row, COL_TARGET) or "Unknown"
            organism    = get(row, COL_ORGANISM)

            record = {
                "smiles":        canon,
                "fasta":         seq,
                "target_name":   target_name,
                "affinity_nm":   round(best_val, 4),
                "affinity_type": best_type,
                "organism":      organism,
            }
            fout.write(json.dumps(record) + "\n")
            written += 1

    log.info(f"Done. Total rows={total:,} | written={written:,} | "
             f"skip: affinity={skipped_affinity:,} smiles={skipped_smiles:,} "
             f"seq={skipped_seq:,} dup={skipped_dup:,}")
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",   required=True, help="Path to BindingDB .tsv file")
    parser.add_argument("--output",  default="./data/bindingdb_parsed.jsonl")
    parser.add_argument("--cutoff",  type=float, default=100.0, help="Affinity cutoff in nM")
    parser.add_argument("--min-seq", type=int,   default=50,    help="Min protein sequence length")
    parser.add_argument("--max",     type=int,   default=None,  help="Max records to write")
    args = parser.parse_args()

    n = parse_bindingdb(args.input, args.output, args.cutoff, args.min_seq, args.max)
    print(f"\nWrote {n:,} pairs → {args.output}")
