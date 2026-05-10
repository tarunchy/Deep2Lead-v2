"""
Shared helpers for dataset building and validation.
"""

import json
import re
from typing import Optional

# Lazy import — RDKit may not be available at import time on all machines
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
    """Rough Lipinski/Veber filter using RDKit."""
    try:
        from rdkit.Chem import Descriptors, rdMolDescriptors
        mol = _get_chem().MolFromSmiles(smiles)
        if mol is None:
            return False
        mw    = Descriptors.MolWt(mol)
        logp  = Descriptors.MolLogP(mol)
        hbd   = rdMolDescriptors.CalcNumHBD(mol)
        hba   = rdMolDescriptors.CalcNumHBA(mol)
        rotb  = rdMolDescriptors.CalcNumRotatableBonds(mol)
        return (mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10 and rotb <= 10)
    except Exception:
        return False


SYSTEM_PROMPT = (
    "You are Deep2Lead's drug discovery AI, specialized in generating novel, "
    "drug-like SMILES molecules for educational drug discovery experiments. "
    "Always output valid SMILES and explain your choices in plain English "
    "suitable for high school students and early researchers."
)


def to_gemma4_chatml(user_text: str, assistant_text: str, system: Optional[str] = None) -> dict:
    """
    Returns a dict with a 'messages' list in Gemma4 ChatML format (text-only).
    """
    msgs = []
    if system:
        msgs.append({"role": "system", "content": [{"type": "text", "text": system}]})
    msgs.append({"role": "user",      "content": [{"type": "text", "text": user_text}]})
    msgs.append({"role": "assistant", "content": [{"type": "text", "text": assistant_text}]})
    return {"messages": msgs}


def apply_processor_template(processor, sample: dict) -> str:
    """
    Given a sample with 'messages' list, apply the Gemma4 processor chat template
    and return the formatted training text (no generation prompt appended).
    """
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


def extract_smiles_from_text(text: str) -> list[str]:
    """Pull out SMILES-looking tokens from a block of text."""
    pattern = r'[A-Za-z0-9@+\-\[\]()=#$.\/\\%]{5,}'
    candidates = re.findall(pattern, text)
    return [s for s in candidates if is_valid_smiles(s)]
