"""Tool functions the chatbot can invoke server-side before calling Gemma."""
import re
from urllib.parse import quote

from rdkit import Chem
from rdkit.Chem import Descriptors, QED, rdMolDescriptors
import requests as http

from services.property_calculator import _sas, _lipinski
from config.settings import PUBCHEM_URL as PUBCHEM, CHEMBL_URL as CHEMBL

TIMEOUT = 12

# ── SMILES extraction ────────────────────────────────────────────────

# Match backtick-wrapped tokens first, then bare SMILES-like strings
_SMILES_RE = re.compile(r'`([^`\s]{4,})`|([A-Za-z\[%][A-Za-z0-9@+\-\[\]\(\)=#%./\\]{5,})')


def extract_smiles(text: str) -> list[str]:
    """Return valid canonical SMILES found in the text."""
    candidates = []
    for m in _SMILES_RE.finditer(text):
        s = m.group(1) or m.group(2)
        try:
            mol = Chem.MolFromSmiles(s)
            if mol:
                candidates.append(Chem.MolToSmiles(mol))
        except Exception:
            pass
    return list(dict.fromkeys(candidates))  # deduplicate, preserve order


# ── Intent detection ─────────────────────────────────────────────────

_NOVELTY_KW = {"novel", "new", "unique", "exist", "known", "database",
                "found", "published", "original", "already"}
_PROPS_KW = {"propert", "qed", "sas", "logp", "mw", "weight", "drug-like",
              "drug like", "lipinski", "synthesiz", "bioavail"}
_VALIDATE_KW = {"valid", "correct", "parse", "smiles check", "check smiles",
                 "canonical", "format"}


def detect_intents(text: str, smiles_list: list[str]) -> list[str]:
    if not smiles_list:
        return []
    low = text.lower()
    intents = []
    if any(w in low for w in _NOVELTY_KW):
        intents.append("novelty")
    if any(w in low for w in _PROPS_KW):
        intents.append("properties")
    if any(w in low for w in _VALIDATE_KW):
        intents.append("validate")
    # Default when SMILES is present but no specific keyword: run novelty + props
    if not intents:
        intents = ["novelty", "properties"]
    return intents


# ── Tools ────────────────────────────────────────────────────────────

def tool_validate(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return f"[VALIDATE] `{smiles}` — INVALID: RDKit could not parse this SMILES string."
    canon = Chem.MolToSmiles(mol)
    atoms = mol.GetNumAtoms()
    return (f"[VALIDATE] `{smiles}` is a VALID SMILES. "
            f"Canonical form: `{canon}` — {atoms} heavy atoms.")


def tool_properties(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return f"[PROPERTIES] Cannot compute — invalid SMILES: `{smiles}`"
    qed = QED.qed(mol)
    sas = _sas(mol)
    logp = Descriptors.MolLogP(mol)
    mw = Descriptors.MolWt(mol)
    hbd = rdMolDescriptors.CalcNumHBD(mol)
    hba = rdMolDescriptors.CalcNumHBA(mol)
    lip = _lipinski(mol)
    assessment = []
    if qed >= 0.6:
        assessment.append("good drug-likeness")
    elif qed >= 0.4:
        assessment.append("moderate drug-likeness")
    else:
        assessment.append("poor drug-likeness")
    if sas <= 3:
        assessment.append("easy to synthesize")
    elif sas <= 5:
        assessment.append("moderately difficult synthesis")
    else:
        assessment.append("difficult synthesis")
    if 0 <= logp <= 3:
        assessment.append("good oral absorption potential")
    return (
        f"[PROPERTIES] `{smiles}`\n"
        f"  QED={qed:.3f} | SAS={sas:.2f} | LogP={logp:.2f} | MW={mw:.1f} Da\n"
        f"  H-donors={hbd} | H-acceptors={hba} | Lipinski={'PASS' if lip else 'FAIL'}\n"
        f"  Assessment: {', '.join(assessment)}."
    )


def tool_novelty_check(smiles: str) -> str:
    results = []

    # 1. PubChem exact match
    try:
        r = http.post(
            f"{PUBCHEM}/compound/smiles/cids/JSON",
            data={"smiles": smiles},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            cids = r.json().get("IdentifierList", {}).get("CID", [])
            if cids:
                results.append(f"PubChem exact match found: CID {cids[0]} "
                                f"(https://pubchem.ncbi.nlm.nih.gov/compound/{cids[0]})")
            else:
                results.append("PubChem: no exact match found.")
        else:
            results.append("PubChem: no exact match found.")
    except Exception as e:
        results.append(f"PubChem exact lookup failed: {e}")

    # 2. PubChem similarity at 90%
    try:
        r = http.post(
            f"{PUBCHEM}/compound/fastsimilarity_2d/smiles/property/IUPACName,IsomericSMILES/JSON",
            data={"smiles": smiles, "Threshold": 90, "MaxRecords": 3},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            props = r.json().get("PropertyTable", {}).get("Properties", [])
            if props:
                names = [p.get("IUPACName", "unnamed") for p in props[:3]]
                results.append(f"PubChem similar (≥90%): {len(props)} compound(s) — {', '.join(names[:2])}")
            else:
                results.append("PubChem similarity (≥90%): no similar compounds found.")
        else:
            results.append("PubChem similarity (≥90%): none found.")
    except Exception as e:
        results.append(f"PubChem similarity failed: {e}")

    # 3. ChEMBL similarity at 90%
    try:
        enc = quote(smiles, safe="")
        r = http.get(f"{CHEMBL}/similarity/{enc}/90?format=json&limit=3", timeout=TIMEOUT)
        if r.status_code == 200:
            mols = r.json().get("molecules", [])
            if mols:
                entries = [
                    f"{m.get('pref_name') or m.get('molecule_chembl_id')} "
                    f"(phase {m.get('max_phase', '?')}, similarity {m.get('similarity', '?')}%)"
                    for m in mols[:3]
                ]
                results.append(f"ChEMBL similar (≥90%): {', '.join(entries)}")
            else:
                results.append("ChEMBL similarity (≥90%): no similar compounds found.")
        else:
            results.append("ChEMBL similarity (≥90%): none found.")
    except Exception as e:
        results.append(f"ChEMBL similarity failed: {e}")

    # Novelty verdict
    has_exact = any("exact match found:" in r for r in results)
    has_similar = any("similar" in r and ("compound(s)" in r or "ChEMBL similar" in r) and "none" not in r and "no similar" not in r for r in results)
    if has_exact:
        verdict = "NOT NOVEL — this exact molecule is already in public databases."
    elif has_similar:
        verdict = "POSSIBLY NOVEL — no exact match, but structurally similar compounds exist (≥90% similarity). Further analysis recommended."
    else:
        verdict = "LIKELY NOVEL — no exact match or highly similar compounds found in PubChem or ChEMBL at ≥90% similarity."

    return (
        f"[NOVELTY CHECK] `{smiles}`\n"
        + "\n".join(f"  • {r}" for r in results)
        + f"\n  Verdict: {verdict}"
    )


# ── Tool runner ──────────────────────────────────────────────────────

import concurrent.futures


def run_tools(smiles: str, intents: list[str]) -> str:
    """Run all applicable tools in parallel and return a combined result block."""
    tasks = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        if "validate" in intents:
            tasks["validate"] = pool.submit(tool_validate, smiles)
        if "properties" in intents:
            tasks["properties"] = pool.submit(tool_properties, smiles)
        if "novelty" in intents:
            tasks["novelty"] = pool.submit(tool_novelty_check, smiles)

    parts = []
    for key in ("validate", "properties", "novelty"):
        if key in tasks:
            try:
                parts.append(tasks[key].result())
            except Exception as e:
                parts.append(f"[{key.upper()}] Error: {e}")

    return "\n\n".join(parts)
