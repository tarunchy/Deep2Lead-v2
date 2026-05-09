"""Protein structure fetching: RCSB PDB, AlphaFold EBI, ESMFold. File-system cache."""
import hashlib
import os
import requests

from config.settings import (
    STRUCTURE_CACHE_DIR, ESMFOLD_URL, ESMFOLD_TIMEOUT, ESMFOLD_MAX_SEQ_LEN,
    ALPHAFOLD_API_URL, RCSB_DOWNLOAD_URL
)

_TIMEOUT = 30


def _ensure_cache_dir():
    os.makedirs(STRUCTURE_CACHE_DIR, exist_ok=True)


def _cache_path(key: str) -> str:
    _ensure_cache_dir()
    return os.path.join(STRUCTURE_CACHE_DIR, f"{key}.pdb")


def fetch_rcsb_pdb(pdb_id: str) -> str | None:
    """Download PDB file from RCSB. Returns PDB text or None."""
    key = f"rcsb_{pdb_id.upper()}"
    cached = _cache_path(key)
    if os.path.exists(cached):
        with open(cached, encoding="utf-8") as f:
            return f.read()
    try:
        url = f"{RCSB_DOWNLOAD_URL}/{pdb_id.upper()}.pdb"
        r = requests.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        pdb_text = r.text
        with open(cached, "w", encoding="utf-8") as f:
            f.write(pdb_text)
        return pdb_text
    except Exception:
        return None


def fetch_alphafold_pdb(uniprot_id: str) -> tuple[str | None, dict | None]:
    """
    Fetch AlphaFold predicted structure for a UniProt accession.
    Returns (pdb_text, meta_dict) or (None, None).
    """
    key = f"af_{uniprot_id.upper()}"
    cached = _cache_path(key)
    meta_cached = cached.replace(".pdb", "_meta.txt")

    if os.path.exists(cached):
        with open(cached, encoding="utf-8") as f:
            pdb_text = f.read()
        meta = {}
        if os.path.exists(meta_cached):
            import json
            with open(meta_cached, encoding="utf-8") as f:
                meta = json.load(f)
        return pdb_text, meta

    try:
        r = requests.get(f"{ALPHAFOLD_API_URL}/{uniprot_id}", timeout=_TIMEOUT)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json()
        if not data:
            return None, None
        entry = data[0]
        pdb_url = entry.get("pdbUrl")
        if not pdb_url:
            return None, None
        pdb_r = requests.get(pdb_url, timeout=60)
        pdb_r.raise_for_status()
        pdb_text = pdb_r.text
        with open(cached, "w", encoding="utf-8") as f:
            f.write(pdb_text)
        meta = {
            "source": "alphafold",
            "uniprot_id": uniprot_id,
            "entry_id": entry.get("entryId"),
            "version": entry.get("latestVersion"),
            "pae_image_url": entry.get("paeImageUrl"),
            "gene": entry.get("gene"),
            "description": entry.get("uniprotDescription"),
        }
        import json
        with open(meta_cached, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        return pdb_text, meta
    except Exception:
        return None, None


def fold_with_esmfold(sequence: str) -> tuple[str | None, str]:
    """
    Fold a custom AA sequence using the free ESMFold API.
    Returns (pdb_text, error_message).
    """
    if len(sequence) > ESMFOLD_MAX_SEQ_LEN:
        return None, f"Sequence too long ({len(sequence)} AA). Maximum is {ESMFOLD_MAX_SEQ_LEN} AA for ESMFold."

    seq_hash = hashlib.sha256(sequence.encode()).hexdigest()[:16]
    key = f"esm_{seq_hash}"
    cached = _cache_path(key)
    if os.path.exists(cached):
        with open(cached, encoding="utf-8") as f:
            return f.read(), ""

    try:
        r = requests.post(
            ESMFOLD_URL,
            data=sequence,
            headers={"Content-Type": "text/plain"},
            timeout=ESMFOLD_TIMEOUT,
        )
        r.raise_for_status()
        pdb_text = r.text
        if not pdb_text.strip().startswith("ATOM") and "ATOM" not in pdb_text:
            return None, "ESMFold returned an unexpected response. The service may be temporarily unavailable."
        with open(cached, "w", encoding="utf-8") as f:
            f.write(pdb_text)
        return pdb_text, ""
    except requests.exceptions.Timeout:
        return None, "ESMFold request timed out. The protein may be too complex or the service is busy. Try a shorter sequence."
    except Exception as e:
        return None, f"ESMFold error: {str(e)}"


def get_best_structure(uniprot_id: str | None, pdb_id: str | None, sequence: str | None) -> tuple[str | None, dict]:
    """
    Priority: experimental PDB → AlphaFold → ESMFold.
    Returns (pdb_text, source_meta).
    """
    # 1. Try known PDB
    if pdb_id:
        pdb_text = fetch_rcsb_pdb(pdb_id)
        if pdb_text:
            return pdb_text, {"source": "rcsb", "pdb_id": pdb_id, "source_label": "Experimental (X-ray/Cryo-EM)"}

    # 2. Try AlphaFold
    if uniprot_id:
        pdb_text, meta = fetch_alphafold_pdb(uniprot_id)
        if pdb_text:
            meta["source_label"] = "AlphaFold2 (AI prediction)"
            return pdb_text, meta

    # 3. ESMFold from sequence
    if sequence:
        pdb_text, err = fold_with_esmfold(sequence)
        if pdb_text:
            return pdb_text, {"source": "esmfold", "source_label": "ESMFold (real-time AI prediction)", "warning": "ESMFold is faster but less accurate than AlphaFold2. Red/yellow regions have lower confidence."}

    return None, {"source": "none", "error": "No structure could be obtained for this target."}


def get_cached_pdb_path(pdb_id: str) -> str | None:
    """Return local file path for a cached PDB, or None."""
    key = f"rcsb_{pdb_id.upper()}"
    p = _cache_path(key)
    return p if os.path.exists(p) else None


def get_pdb_text_by_key(key: str) -> str | None:
    """Read cached PDB by raw key (for serving to frontend)."""
    p = _cache_path(key)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return f.read()
    return None
