"""
Download high-affinity protein-SMILES pairs from ChEMBL and UniProt REST APIs.
No HuggingFace dependency — uses EBI ChEMBL API directly.

Strategy:
  1. Page through ChEMBL /activity endpoint: IC50 ≤ 100 nM, single-protein targets
  2. Resolve each target's UniProt accession via ChEMBL /target endpoint
  3. Fetch protein sequence from UniProt FASTA API
  4. Cache UniProt sequences locally (most targets appear many times)
  5. Validate SMILES with RDKit; drop invalid
  6. Save incrementally to disk so reruns resume without re-downloading

ChEMBL API docs: https://www.ebi.ac.uk/chembl/api/data/
UniProt API docs: https://rest.uniprot.org/

Usage:
    python3 data/download_chembl.py [--max-pairs 65000] [--output ./data/chembl_bindingdb_pairs.jsonl]
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── API base URLs ──────────────────────────────────────────────────────────────
CHEMBL_API   = "https://www.ebi.ac.uk/chembl/api/data"
UNIPROT_API  = "https://rest.uniprot.org/uniprotkb"

# ── Limits ─────────────────────────────────────────────────────────────────────
CHEMBL_PAGE_SIZE     = 1000       # max per ChEMBL request
RATE_LIMIT_SLEEP     = 0.25       # seconds between ChEMBL pages (be polite)
UNIPROT_SLEEP        = 0.1        # seconds between UniProt fetches
REQUEST_TIMEOUT      = 30         # seconds per HTTP request
MAX_RETRIES          = 5

# ── RDKit lazy import ──────────────────────────────────────────────────────────
_Chem = None
def _get_chem():
    global _Chem
    if _Chem is None:
        from rdkit import Chem as _c
        _Chem = _c
    return _Chem

def _is_valid_smiles(smiles: str) -> bool:
    try:
        mol = _get_chem().MolFromSmiles(smiles)
        return mol is not None
    except Exception:
        return False


def _make_session() -> requests.Session:
    """HTTP session with exponential backoff retry."""
    s = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"Accept": "application/json"})
    return s


SESSION = _make_session()

# ── UniProt sequence cache ─────────────────────────────────────────────────────
_uniprot_cache: dict[str, str] = {}
_uniprot_miss:  set[str]       = set()   # accessions we've already tried and failed

def _fetch_uniprot_sequence(accession: str) -> str | None:
    """Return amino acid sequence for a UniProt accession, or None if not found."""
    if accession in _uniprot_cache:
        return _uniprot_cache[accession]
    if accession in _uniprot_miss:
        return None
    try:
        url = f"{UNIPROT_API}/{accession}.fasta"
        r = SESSION.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code == 404:
            _uniprot_miss.add(accession)
            return None
        r.raise_for_status()
        lines = r.text.strip().split("\n")
        seq = "".join(l for l in lines if not l.startswith(">"))
        if len(seq) < 10:
            _uniprot_miss.add(accession)
            return None
        _uniprot_cache[accession] = seq
        time.sleep(UNIPROT_SLEEP)
        return seq
    except Exception as e:
        log.warning(f"  UniProt fetch failed for {accession}: {e}")
        _uniprot_miss.add(accession)
        return None


# ── ChEMBL target → UniProt accession cache ────────────────────────────────────
_target_cache: dict[str, tuple[str, str]] = {}   # chembl_id → (uniprot_acc, target_name)
_target_miss:  set[str] = set()

def _fetch_target_info(target_chembl_id: str) -> tuple[str, str] | None:
    """Return (uniprot_accession, target_name) for a ChEMBL target, or None."""
    if target_chembl_id in _target_cache:
        return _target_cache[target_chembl_id]
    if target_chembl_id in _target_miss:
        return None
    try:
        url = f"{CHEMBL_API}/target/{target_chembl_id}.json"
        r = SESSION.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code == 404:
            _target_miss.add(target_chembl_id)
            return None
        r.raise_for_status()
        data = r.json()

        pref_name = data.get("pref_name", "Unknown")

        # Extract UniProt accession from target_components
        components = data.get("target_components", [])
        accession  = None
        for comp in components:
            for xref in comp.get("target_component_xrefs", []):
                if xref.get("xref_src_db") == "UniProt":
                    accession = xref.get("xref_id")
                    break
            if accession:
                break

        if not accession:
            _target_miss.add(target_chembl_id)
            return None

        result = (accession, pref_name)
        _target_cache[target_chembl_id] = result
        return result
    except Exception as e:
        log.warning(f"  ChEMBL target fetch failed for {target_chembl_id}: {e}")
        _target_miss.add(target_chembl_id)
        return None


# ── Main ChEMBL activity paginator ────────────────────────────────────────────

def download_chembl_pairs(max_pairs: int, output_path: str, ic50_cutoff_nm: float = 100.0) -> int:
    """
    Page through ChEMBL activities, resolve sequences, filter, and write to JSONL.
    Returns count of pairs written.

    Output format per line:
        {"fasta": "...", "smiles": "...", "target_name": "...", "ic50_nm": 42.0}
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Count existing pairs so we can resume
    existing = 0
    if out.exists():
        with open(out) as f:
            existing = sum(1 for l in f if l.strip())
        log.info(f"Resuming: {existing} pairs already written to {output_path}")
        if existing >= max_pairs:
            log.info("Target already reached — nothing to do.")
            return existing

    written   = existing
    offset    = 0
    seen_smiles: set[str] = set()

    # Load already-written SMILES to avoid duplicates on resume
    if existing > 0:
        with open(out) as f:
            for line in f:
                try:
                    seen_smiles.add(json.loads(line)["smiles"])
                except Exception:
                    pass

    log.info(f"Downloading ChEMBL pairs: target={max_pairs}, IC50≤{ic50_cutoff_nm}nM")

    params = {
        "standard_type":     "IC50",
        "standard_units":    "nM",
        "standard_value__lte": ic50_cutoff_nm,
        "target_type":       "SINGLE PROTEIN",
        "assay_type":        "B",         # binding assays only
        "standard_relation": "=",
        "format":            "json",
        "limit":             CHEMBL_PAGE_SIZE,
    }

    with open(out, "a") as fout:
        while written < max_pairs:
            params["offset"] = offset
            try:
                r = SESSION.get(f"{CHEMBL_API}/activity.json", params=params, timeout=REQUEST_TIMEOUT)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log.error(f"ChEMBL activity fetch failed at offset {offset}: {e}")
                time.sleep(10)
                continue

            activities = data.get("activities", [])
            if not activities:
                log.info("No more ChEMBL activities — download complete.")
                break

            page_written = 0
            for act in activities:
                if written >= max_pairs:
                    break

                smiles          = (act.get("canonical_smiles") or "").strip()
                target_cid      = (act.get("target_chembl_id") or "").strip()
                standard_value  = act.get("standard_value")

                if not smiles or not target_cid:
                    continue
                if smiles in seen_smiles:
                    continue
                if not _is_valid_smiles(smiles):
                    continue

                try:
                    ic50_val = float(standard_value)
                except (TypeError, ValueError):
                    continue

                # Resolve target → UniProt → sequence
                target_info = _fetch_target_info(target_cid)
                if target_info is None:
                    continue
                uniprot_acc, target_name = target_info

                sequence = _fetch_uniprot_sequence(uniprot_acc)
                if sequence is None:
                    continue

                record = {
                    "fasta":       sequence,
                    "smiles":      smiles,
                    "target_name": target_name,
                    "ic50_nm":     ic50_val,
                }
                fout.write(json.dumps(record) + "\n")
                fout.flush()

                seen_smiles.add(smiles)
                written      += 1
                page_written += 1

            total_available = data.get("page_meta", {}).get("total_count", "?")
            log.info(
                f"  offset={offset:>7} | page_written={page_written:>4} | "
                f"total_written={written:>6}/{max_pairs} | "
                f"chembl_total={total_available}"
            )

            offset += CHEMBL_PAGE_SIZE
            time.sleep(RATE_LIMIT_SLEEP)

            # ChEMBL returns None page_meta when exhausted
            if not data.get("page_meta", {}).get("next"):
                log.info("ChEMBL: reached last page.")
                break

    log.info(f"ChEMBL download complete. Wrote {written} pairs to {output_path}")
    log.info(f"UniProt cache hits: {len(_uniprot_cache)} | misses: {len(_uniprot_miss)}")
    log.info(f"Target cache hits: {len(_target_cache)} | misses: {len(_target_miss)}")
    return written


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pairs",  type=int,   default=65_000)
    parser.add_argument("--output",     default="./data/chembl_bindingdb_pairs.jsonl")
    parser.add_argument("--ic50-cutoff", type=float, default=100.0)
    args = parser.parse_args()

    n = download_chembl_pairs(
        max_pairs=args.max_pairs,
        output_path=args.output,
        ic50_cutoff_nm=args.ic50_cutoff,
    )
    print(f"\nDone. {n} pairs saved to {args.output}")
    print("Next: python3 data/download_datasets_v2.py")
