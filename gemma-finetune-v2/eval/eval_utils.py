"""
Shared evaluation utilities: chemistry metrics, Tanimoto, diversity, MAMMAL client.
"""

import re
import statistics
from typing import Optional


# ── SMILES / RDKit ─────────────────────────────────────────────────────────────

def get_mol(smiles: str):
    try:
        from rdkit import Chem
        return Chem.MolFromSmiles(smiles)
    except Exception:
        return None


def canonical(smiles: str) -> Optional[str]:
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        return Chem.MolToSmiles(mol) if mol else None
    except Exception:
        return None


def extract_smiles_from_text(text: str) -> list[str]:
    """Extract all valid SMILES tokens from free text."""
    from rdkit import Chem
    candidates = re.findall(r'[A-Za-z0-9@+\-\[\]()=#$.\/\\%]{5,}', text)
    out = []
    for s in candidates:
        mol = Chem.MolFromSmiles(s)
        if mol is not None:
            out.append(Chem.MolToSmiles(mol))
    return out


# ── Lipinski / drug-likeness ───────────────────────────────────────────────────

def lipinski(smiles: str) -> dict:
    """Return Ro5 descriptors and pass/fail for a SMILES."""
    mol = get_mol(smiles)
    if mol is None:
        return {"valid": False}
    from rdkit.Chem import Descriptors, rdMolDescriptors
    mw   = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    hbd  = rdMolDescriptors.CalcNumHBD(mol)
    hba  = rdMolDescriptors.CalcNumHBA(mol)
    tpsa = rdMolDescriptors.CalcTPSA(mol)
    rotb = rdMolDescriptors.CalcNumRotatableBonds(mol)
    ro5  = (mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10)
    return {
        "valid": True, "mw": round(mw, 1), "logp": round(logp, 2),
        "hbd": hbd, "hba": hba, "tpsa": round(tpsa, 1), "rotb": rotb,
        "ro5_pass": ro5,
    }


def qed(smiles: str) -> Optional[float]:
    try:
        from rdkit.Chem import QED as RDQED
        mol = get_mol(smiles)
        return round(RDQED.qed(mol), 4) if mol else None
    except Exception:
        return None


def sas(smiles: str) -> Optional[float]:
    try:
        from rdkit.Contrib.SA_Score import sascorer
        mol = get_mol(smiles)
        return round(sascorer.calculateScore(mol), 4) if mol else None
    except Exception:
        return None


# ── Tanimoto / novelty / diversity ────────────────────────────────────────────

def _fp(smiles: str):
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
        mol = Chem.MolFromSmiles(smiles)
        return AllChem.GetMorganFingerprintAsBitVect(mol, 2, 2048) if mol else None
    except Exception:
        return None


def tanimoto(smi_a: str, smi_b: str) -> float:
    try:
        from rdkit import DataStructs
        fa, fb = _fp(smi_a), _fp(smi_b)
        if fa is None or fb is None:
            return 0.0
        return round(DataStructs.TanimotoSimilarity(fa, fb), 4)
    except Exception:
        return 0.0


def novelty_vs_set(generated: list[str], reference: list[str], threshold: float = 0.4) -> float:
    """
    Fraction of generated SMILES that are novel (max Tanimoto < threshold)
    relative to the reference set.
    """
    if not generated or not reference:
        return 1.0
    ref_fps = [_fp(s) for s in reference]
    ref_fps = [f for f in ref_fps if f is not None]
    if not ref_fps:
        return 1.0
    try:
        from rdkit import DataStructs
        novel = 0
        for smi in generated:
            fp = _fp(smi)
            if fp is None:
                continue
            sims = DataStructs.BulkTanimotoSimilarity(fp, ref_fps)
            if max(sims) < threshold:
                novel += 1
        return round(novel / len(generated), 4)
    except Exception:
        return 1.0


def internal_diversity(smiles_list: list[str], sample_size: int = 200) -> float:
    """
    Mean pairwise Tanimoto DISTANCE (1 - similarity) within the set.
    1.0 = maximally diverse, 0.0 = all identical.
    """
    import random
    try:
        from rdkit import DataStructs
        fps = [_fp(s) for s in smiles_list if _fp(s) is not None]
        if len(fps) < 2:
            return 0.0
        if len(fps) > sample_size:
            fps = random.sample(fps, sample_size)
        distances = []
        for i in range(len(fps)):
            sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps[:i])
            distances.extend(1.0 - s for s in sims)
        return round(statistics.mean(distances), 4) if distances else 0.0
    except Exception:
        return 0.0


# ── MAMMAL API client (thin wrapper for eval use) ─────────────────────────────

import os
import requests

MAMMAL_HOST = os.getenv("MAMMAL_API_HOST", "192.168.86.20")
MAMMAL_PORT = int(os.getenv("MAMMAL_API_PORT", "8090"))
MAMMAL_BASE = f"http://{MAMMAL_HOST}:{MAMMAL_PORT}"
MAMMAL_TIMEOUT = int(os.getenv("MAMMAL_TIMEOUT", "120"))


def mammal_score_batch(fasta: str, smiles_list: list[str]) -> list[dict]:
    """
    Score a list of SMILES against a single protein FASTA using MAMMAL API.
    Returns list of {"smiles", "pkd", "score", "is_binder"} dicts.
    Falls back to {"pkd": None, "score": None} if API unreachable.
    """
    results = []
    try:
        payload = {"pairs": [{"fasta": fasta, "smiles": s} for s in smiles_list]}
        r = requests.post(f"{MAMMAL_BASE}/predict-batch", json=payload, timeout=MAMMAL_TIMEOUT)
        r.raise_for_status()
        api_results = r.json()["results"]
        for smi, res in zip(smiles_list, api_results):
            results.append({
                "smiles":    smi,
                "pkd":       res["pkd"],
                "score":     res["score"],
                "is_binder": res["is_binder"],
            })
    except Exception as e:
        for smi in smiles_list:
            results.append({"smiles": smi, "pkd": None, "score": None, "is_binder": False,
                            "error": str(e)})
    return results


def mammal_available() -> bool:
    try:
        r = requests.get(f"{MAMMAL_BASE}/health", timeout=5)
        return r.json().get("status") == "ready"
    except Exception:
        return False


# ── Table formatting ───────────────────────────────────────────────────────────

def fmt_table(rows: list[dict], cols: list[str]) -> str:
    """Simple markdown table from list of dicts."""
    header = "| " + " | ".join(cols) + " |"
    sep    = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines  = [header, sep]
    for row in rows:
        cells = []
        for c in cols:
            val = row.get(c, "—")
            cells.append(f"{val:.3f}" if isinstance(val, float) else str(val))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
