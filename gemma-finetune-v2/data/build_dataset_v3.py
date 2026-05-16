"""
Build merged training dataset v3.

Sources (target totals):
  1. BindingDB high-affinity pairs      ~120K  (Kd/Ki/IC50 ≤ 100 nM, deduplicated)
  2. Existing ChEMBL pairs              ~65K   (already downloaded)
  3. Mol-Instructions reasoning         ~25K   (from local git clone)
  4. MOSES contextualized               ~10K   (syntax baseline)
  5. Deep2Lead custom v2                ~60    (curated examples)

Total target: ~220K records

Format: rationale-first ChatML for BindingDB/ChEMBL,
        standard ChatML for Mol-Instructions/MOSES.

Usage:
  python3 data/build_dataset_v3.py
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import SEED, MERGED_DATASET_PATH, CHEMBL_PAIRS_PATH, CUSTOM_DATASET_PATH
from data.dataset_utils import (
    to_rationale_chatml, to_gemma4_chatml, save_jsonl, load_jsonl,
    is_valid_smiles, SYSTEM_PROMPT,
)

random.seed(SEED)

# ── Paths ──────────────────────────────────────────────────────────────────────
BINDINGDB_JSONL      = os.getenv("BINDINGDB_JSONL", "./data/bindingdb_parsed.jsonl")
MOL_INSTRUCTIONS_JSONL = "./data/mol_instructions.jsonl"
MOSES_SAMPLES        = 10_000
OUTPUT_PATH          = "./data/merged_finetune_v3.jsonl"

# ── Rationale templates (target-aware) ────────────────────────────────────────
_RATIONALE_TEMPLATES = [
    ("hydrophobic",
     "The binding pocket features a hydrophobic cleft lined with aromatic residues. "
     "The scaffold's flat aromatic core enables pi-pi stacking while a polar tail "
     "anchors a key hydrogen bond with the backbone."),
    ("kinase",
     "This kinase target presents a conserved ATP-binding hinge region. "
     "An N-heterocyclic hinge binder combined with a hydrophobic back-pocket group "
     "achieves both selectivity and nanomolar potency."),
    ("protease",
     "The aspartyl/serine protease active site contains a catalytic dyad/triad. "
     "A transition-state mimic scaffold occupies the S1-S3 subsites, "
     "while a compact P2 group fills the hydrophobic pocket."),
    ("allosteric",
     "Structural analysis reveals an allosteric pocket adjacent to the active site. "
     "A rigid bicyclic core locks the bioactive conformation; "
     "a morpholine tail balances lipophilicity and aqueous solubility."),
    ("gpcr",
     "This GPCR target has a deep orthosteric binding pocket within the transmembrane bundle. "
     "A basic amine mimics the endogenous ligand's ionic interaction with Asp, "
     "while a lipophilic tail fills the hydrophobic sub-pocket."),
    ("fragment",
     "Fragment-based design guided scaffold selection: a small MW 150-250 Da "
     "fragment with measurable affinity was optimized by growing into adjacent pockets, "
     "maintaining ligand efficiency above 0.3 kcal/mol per heavy atom."),
    ("covalent",
     "A targeted covalent strategy exploits a non-conserved cysteine near the active site. "
     "An electrophilic warhead (acrylamide) reacts irreversibly, "
     "while the recognition scaffold confers selectivity over off-targets."),
    ("ppi",
     "This protein-protein interaction target has a shallow, featureless interface. "
     "A helical mimetic stabilizes the bioactive conformation, "
     "with strategic substituents projecting hot-spot pharmacophores."),
]


def _pick_rationale(target_name: str) -> str:
    name_lower = target_name.lower()
    if any(k in name_lower for k in ["kinase", "kdr", "egfr", "abl", "cdk", "braf"]):
        return next(r for tag, r in _RATIONALE_TEMPLATES if tag == "kinase")
    if any(k in name_lower for k in ["protease", "mpro", "nsp5", "hiv", "bace", "dpp"]):
        return next(r for tag, r in _RATIONALE_TEMPLATES if tag == "protease")
    if any(k in name_lower for k in ["receptor", "gpcr", "adenosine", "dopamine"]):
        return next(r for tag, r in _RATIONALE_TEMPLATES if tag == "gpcr")
    # Default: random
    return random.choice(_RATIONALE_TEMPLATES)[1]


def _bindingdb_to_chatml(fasta: str, smiles: str, target_name: str,
                          affinity_nm: float, affinity_type: str) -> dict:
    seq_preview = fasta[:150]
    aff_str = f"{affinity_type} = {affinity_nm:.1f} nM"
    user = (
        f"Target: {target_name}\n"
        f"Protein sequence (first 150 AA): {seq_preview}\n"
        f"Measured binding affinity: {aff_str}\n"
        "Design a small molecule drug candidate with high binding affinity to this target. "
        "First explain your structural reasoning (binding pocket analysis, key interactions), "
        "then provide the SMILES.\n"
        "Requirements: MW 200-500 Da, QED > 0.50, SAS ≤ 5.0, Lipinski Ro5 compliant."
    )
    rationale = _pick_rationale(target_name)
    return to_rationale_chatml(user, rationale, [smiles], system=SYSTEM_PROMPT)


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_bindingdb(path: str, max_records: int = 150_000) -> list:
    if not os.path.exists(path):
        print(f"  BindingDB JSONL not found: {path} — skipping")
        return []
    records = []
    with open(path) as f:
        for line in f:
            if len(records) >= max_records:
                break
            try:
                row = json.loads(line)
                fasta  = row.get("fasta", "").strip()
                smiles = row.get("smiles", "").strip()
                name   = row.get("target_name", "Unknown")
                aff    = row.get("affinity_nm", 0.0)
                atyp   = row.get("affinity_type", "IC50")
                if fasta and smiles and len(fasta) >= 50:
                    records.append(_bindingdb_to_chatml(fasta, smiles, name, aff, atyp))
            except Exception:
                pass
    print(f"  BindingDB: {len(records):,} records")
    return records


def load_chembl(path: str, max_records: int = 65_000) -> list:
    """Load pre-downloaded ChEMBL pairs (v2 format)."""
    if not os.path.exists(path):
        print(f"  ChEMBL JSONL not found: {path} — skipping")
        return []
    from data.download_datasets_v2 import _chembl_rationale
    records = []
    with open(path) as f:
        for line in f:
            if len(records) >= max_records:
                break
            try:
                row = json.loads(line)
                fasta  = row.get("fasta", "").strip()
                smiles = row.get("smiles", "").strip()
                name   = row.get("target_name", "Unknown")
                if fasta and smiles and is_valid_smiles(smiles):
                    records.append(_chembl_rationale(fasta, smiles, name))
            except Exception:
                pass
    print(f"  ChEMBL:    {len(records):,} records")
    return records


def load_mol_instructions(path: str) -> list:
    if not os.path.exists(path):
        print(f"  Mol-Instructions JSONL not found: {path} — skipping")
        return []
    records = load_jsonl(path)
    print(f"  Mol-Instructions: {len(records):,} records")
    return records


def load_moses(n: int) -> list:
    _PROMPTS = [
        "Design a drug-like molecule with balanced LogP and MW. Provide SMILES and explain key structural features.",
        "Generate a novel small molecule satisfying Lipinski's Rule of 5. Output SMILES with brief rationale.",
        "Propose a new drug scaffold: MW < 450 Da, at least one ring, one hydrogen-bond donor. Provide SMILES.",
        "Create a fragment-like molecule (MW 150-300, HAC ≤ 25) for fragment-based drug discovery. Output SMILES.",
        "Generate a bioisostere of a simple aromatic acid scaffold. Provide SMILES and explain the replacement.",
        "Design a CNS-penetrant molecule: MW < 400, LogP 1-3, PSA < 80 Å². Explain BBB criteria, then SMILES.",
        "Generate a kinase-focused scaffold with an N-heterocyclic hinge binder. Output SMILES with rationale.",
    ]
    try:
        from datasets import load_dataset
        ds = list(load_dataset("katielink/moses", split="train", trust_remote_code=False))
        random.shuffle(ds)
        ds = ds[:n]
        records = []
        for row in ds:
            smiles = (row.get("smiles") or row.get("SMILES") or "").strip()
            if smiles and is_valid_smiles(smiles):
                prompt = random.choice(_PROMPTS)
                asst = (
                    f"Rationale: This molecule balances lipophilicity and MW within drug-like space. "
                    f"The scaffold supports modification at multiple positions for SAR exploration.\n\n"
                    f"SMILES: {smiles}"
                )
                records.append(to_gemma4_chatml(prompt, asst, system=SYSTEM_PROMPT))
        print(f"  MOSES:     {len(records):,} records")
        return records
    except Exception as e:
        print(f"  MOSES failed: {e}")
        return []


def load_custom() -> list:
    if not os.path.exists(CUSTOM_DATASET_PATH):
        return []
    records = load_jsonl(CUSTOM_DATASET_PATH)
    print(f"  Custom v2: {len(records):,} records")
    return records


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Building Deep2Lead v3 merged dataset")
    print("=" * 60)

    print("\n[1/5] BindingDB high-affinity pairs ...")
    bindingdb = load_bindingdb(BINDINGDB_JSONL, max_records=150_000)

    print("\n[2/5] ChEMBL pairs ...")
    chembl = load_chembl(CHEMBL_PAIRS_PATH, max_records=65_000)

    print("\n[3/5] Mol-Instructions ...")
    mol_inst = load_mol_instructions(MOL_INSTRUCTIONS_JSONL)

    print("\n[4/5] MOSES ...")
    moses = load_moses(MOSES_SAMPLES)

    print("\n[5/5] Custom Deep2Lead ...")
    custom = load_custom()

    # Merge and shuffle
    all_records = bindingdb + chembl + mol_inst + moses + custom
    random.shuffle(all_records)

    # Save
    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    save_jsonl(all_records, OUTPUT_PATH)

    total = len(all_records)
    print(f"\n{'='*60}")
    print(f"V3 DATASET SUMMARY")
    print(f"{'='*60}")
    print(f"  BindingDB:         {len(bindingdb):>7,}  ({100*len(bindingdb)/max(total,1):.1f}%)")
    print(f"  ChEMBL:            {len(chembl):>7,}  ({100*len(chembl)/max(total,1):.1f}%)")
    print(f"  Mol-Instructions:  {len(mol_inst):>7,}  ({100*len(mol_inst)/max(total,1):.1f}%)")
    print(f"  MOSES:             {len(moses):>7,}  ({100*len(moses)/max(total,1):.1f}%)")
    print(f"  Custom:            {len(custom):>7,}  ({100*len(custom)/max(total,1):.1f}%)")
    print(f"  TOTAL:             {total:>7,}")
    print(f"  Saved → {OUTPUT_PATH}")
    print(f"{'='*60}")
    print(f"\nNext: python3 train/finetune_gemma4_v3.py")
