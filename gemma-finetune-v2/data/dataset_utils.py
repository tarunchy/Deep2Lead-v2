"""
Shared helpers for v2 dataset building and validation.
Key v2 change: SYSTEM_PROMPT_V2 enforces rationale-first responses
so the model learns protein→scaffold chain-of-thought mapping.
"""

import json
import re
from typing import Optional

try:
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.error")
    RDLogger.DisableLog("rdApp.warning")
except Exception:
    pass

_Chem = None


def _get_chem():
    global _Chem
    if _Chem is None:
        from rdkit import Chem as _c
        _Chem = _c
    return _Chem


def is_valid_smiles(smiles: str) -> bool:
    try:
        mol = _get_chem().MolFromSmiles(smiles)
        return mol is not None
    except Exception:
        return False


def drug_like_filter(smiles: str) -> bool:
    try:
        from rdkit.Chem import Descriptors, rdMolDescriptors
        mol = _get_chem().MolFromSmiles(smiles)
        if mol is None:
            return False
        mw   = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd  = rdMolDescriptors.CalcNumHBD(mol)
        hba  = rdMolDescriptors.CalcNumHBA(mol)
        rotb = rdMolDescriptors.CalcNumRotatableBonds(mol)
        return (mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10 and rotb <= 10)
    except Exception:
        return False


# v2: system prompt emphasizes chain-of-thought rationale before SMILES output
SYSTEM_PROMPT = (
    "You are Deep2Lead's drug discovery AI v2. When given a protein target or biological context, "
    "first reason about the binding pocket geometry, key residues, and desired physicochemical profile "
    "(2-3 sentences), then output novel drug-like SMILES molecules. Always label your reasoning as "
    "'Rationale:' and your molecules as 'SMILES:'. Explain choices in plain English suitable for "
    "high school students and early researchers. Prioritize selectivity, low toxicity, and synthetic accessibility."
)


def to_gemma4_chatml(user_text: str, assistant_text: str, system: Optional[str] = None) -> dict:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": [{"type": "text", "text": system}]})
    msgs.append({"role": "user",      "content": [{"type": "text", "text": user_text}]})
    msgs.append({"role": "assistant", "content": [{"type": "text", "text": assistant_text}]})
    return {"messages": msgs}


def to_rationale_chatml(user_text: str, rationale: str, smiles_list: list[str],
                         system: Optional[str] = None) -> dict:
    """
    v2 format: assistant always leads with rationale before SMILES.
    Forces chain-of-thought protein→scaffold mapping.
    """
    numbered = "\n".join(f"SMILES: {s}" for s in smiles_list)
    assistant_text = f"Rationale: {rationale}\n\n{numbered}"
    return to_gemma4_chatml(user_text, assistant_text, system)


def apply_processor_template(processor, sample: dict) -> str:
    return processor.apply_chat_template(
        sample["messages"],
        tokenize=False,
        add_generation_prompt=False,
    )


def save_jsonl(records: list, path: str):
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"Saved {len(records):,} records → {path}")


def load_jsonl(path: str) -> list:
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


_SMILES_CHAR = re.compile(r'[0-9\[\]=#@\\/]')

def extract_smiles_from_text(text: str) -> list[str]:
    candidates = re.findall(r'[A-Za-z0-9@+\-\[\]()=#$.\/\\%]{5,}', text)
    return [s for s in candidates if _SMILES_CHAR.search(s) and is_valid_smiles(s)]
