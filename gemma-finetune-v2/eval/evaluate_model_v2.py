#!/usr/bin/env python3
"""
Evaluate the v2 fine-tuned Gemma4-E2B model on drug discovery tasks.
v2 targets (stricter than v1):
  - SMILES validity  ≥ 95%  (v1 target: 90%)
  - Average QED      ≥ 0.60 (v1 target: 0.45)
  - Uniqueness       ≥ 90%
  - Average SAS      ≤ 4.5

v2 eval also checks rationale output format and target-conditioned diversity.

Usage:
    python3 eval/evaluate_model_v2.py [--lora-path ./drug_discovery/lora/gemma4_e2b_drug_v2]
                                       [--n-prompts 30]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import MODEL_NAME, MAX_SEQ_LENGTH, OUTPUT_DIR
from data.dataset_utils import is_valid_smiles, SYSTEM_PROMPT

# v2 evaluation targets (stricter)
VALIDITY_TARGET  = 0.95
QED_TARGET       = 0.60
UNIQUE_TARGET    = 0.90
SAS_TARGET       = 4.5

EVAL_PROMPTS = [
    # Target-conditioned (primary v2 metric)
    "Target protein (first 120 AA): MESLVPGFNEKTHVQLSLPVLQVRDVLVRGFGDSVEEVLSEARQHLK\n"
    "Design 4 drug candidates for SARS-CoV-2 Main Protease. First explain your rationale, then provide SMILES.",

    "Target: EGFR Kinase (T790M resistance mutant)\n"
    "Protein sequence: MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFE\n"
    "Design 3 SMILES that overcome the T790M gatekeeper mutation. Provide rationale first.",

    "Target: BRAF V600E (melanoma)\n"
    "Protein sequence: MAHHHHHHHHHHHIEGRHHHKLVWFPGGAETAERAGQIRGASMKFVA\n"
    "Generate 4 selective inhibitor SMILES. Start with structural reasoning.",

    "Target: BCR-ABL (CML, T315I gatekeeper mutant)\n"
    "Protein sequence: MGSSHHHHHHSSGLVPRGSHMRGPNARRGPPA\n"
    "Generate 3 third-generation inhibitor SMILES with rationale.",

    "Target: HIV-1 Protease\n"
    "Protein sequence: PQITLWQRPLVTIKIGGQLKEALLDTGADDTVLEEMSLPGRWK\n"
    "Generate 4 protease inhibitor SMILES using a hydroxyethylamine isostere strategy. Rationale first.",

    # Scaffold hop prompts
    "Reference drug: Erlotinib (SMILES: C#Cc1cccc(c1)Nc2ncnc3cc(OCC)c(OCC)cc23)\n"
    "Perform a scaffold hop: design 3 SMILES with a different core ring system but preserved pharmacophore. Explain the bioisostere strategy.",

    "Reference drug: Imatinib (SMILES: Cc1ccc(cc1Nc2nccc(n2)c3cccnc3)NC(=O)c4ccc(cc4)CN5CCN(CC5)C)\n"
    "Design 2 structurally distinct BCR-ABL inhibitor scaffolds. Rationale before SMILES.",

    # Property-conditioned
    "Generate 5 drug-like SMILES with MW 350-400 Da, LogP 2.0-3.5, QED > 0.65, and at least one hydrogen-bond donor. "
    "First explain your design strategy.",

    "Design 4 CNS-penetrant molecules: MW < 420, LogP 1-3, PSA < 90 Å², max 1 HBD. "
    "Reason about BBB permeability criteria before providing SMILES.",

    # General chemistry
    "Generate 5 diverse SMILES for kinase inhibitor candidates with an aromatic hinge-binding scaffold.",
]


def compute_rdkit_metrics(smiles_list: list[str]) -> dict:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, QED as RDKitQED
    try:
        from rdkit.Contrib.SA_Score import sascorer
        has_sas = True
    except Exception:
        has_sas = False

    valid, qeds, sass = [], [], []
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            continue
        valid.append(smi)
        qeds.append(RDKitQED.qed(mol))
        if has_sas:
            sass.append(sascorer.calculateScore(mol))

    n = len(smiles_list)
    result = {
        "total":    n,
        "valid":    len(valid),
        "validity": len(valid) / n if n else 0,
        "unique":   len(set(valid)) / max(len(valid), 1),
        "avg_qed":  sum(qeds) / len(qeds) if qeds else 0,
    }
    if sass:
        result["avg_sas"] = sum(sass) / len(sass)
    return result


def check_rationale_format(response: str) -> bool:
    """v2 check: does response include 'Rationale:' before SMILES?"""
    lower = response.lower()
    rat_pos   = lower.find("rationale:")
    smiles_pos = lower.find("smiles:")
    return rat_pos != -1 and (smiles_pos == -1 or rat_pos < smiles_pos)


def run_eval(lora_path: str, n_prompts: int):
    print(f"\nLoading v2 fine-tuned model ...")
    print(f"  Base:  {MODEL_NAME}")
    print(f"  LoRA:  {lora_path}\n")

    from unsloth import FastModel

    model, processor = FastModel.from_pretrained(
        model_name=lora_path,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=True,
        dtype=None,
    )
    FastModel.for_inference(model)

    prompts = (EVAL_PROMPTS * 10)[:n_prompts]
    all_smiles  = []
    rationale_hits = 0
    results_per_prompt = []

    import torch
    for i, prompt in enumerate(prompts):
        print(f"[{i+1}/{n_prompts}] {prompt[:75]}...")
        messages = [
            {"role": "system",    "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
            {"role": "user",      "content": [{"type": "text", "text": prompt}]},
        ]
        inputs = processor.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt",
            return_dict=True, tokenize=True,
        ).to("cuda")

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=384,
                do_sample=True,
                temperature=0.85,
                top_p=0.92,
                top_k=50,
                repetition_penalty=1.3,
            )

        generated = outputs[0][inputs["input_ids"].shape[-1]:]
        response  = processor.decode(generated, skip_special_tokens=True).strip()

        from data.dataset_utils import extract_smiles_from_text
        smiles_in_response = extract_smiles_from_text(response)
        all_smiles.extend(smiles_in_response)

        has_rationale = check_rationale_format(response)
        if has_rationale:
            rationale_hits += 1

        results_per_prompt.append({
            "prompt":        prompt,
            "response":      response,
            "smiles":        smiles_in_response,
            "has_rationale": has_rationale,
        })
        print(f"  → {len(smiles_in_response)} SMILES | rationale={'yes' if has_rationale else 'no'}")

    # Aggregate metrics
    print(f"\n{'='*60}")
    print(f"V2 EVALUATION RESULTS ({n_prompts} prompts, {len(all_smiles)} extracted SMILES)")
    print(f"{'='*60}")
    metrics = compute_rdkit_metrics(all_smiles)
    rationale_rate = rationale_hits / n_prompts if n_prompts else 0
    metrics["rationale_format_rate"] = rationale_rate

    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:<28} {v:.3f}")
        else:
            print(f"  {k:<28} {v}")

    # Save results
    out_path = os.path.join(os.path.dirname(lora_path), "eval_results_v2.json")
    with open(out_path, "w") as f:
        json.dump({"metrics": metrics, "per_prompt": results_per_prompt}, f, indent=2)
    print(f"\nFull results saved → {out_path}")

    # Pass/fail vs v2 targets
    validity = metrics.get("validity", 0)
    avg_qed  = metrics.get("avg_qed", 0)
    unique   = metrics.get("unique", 0)
    avg_sas  = metrics.get("avg_sas", 99)
    rat_rate = metrics.get("rationale_format_rate", 0)

    print(f"\n{'='*60}")
    print(f"V2 TARGET PASS/FAIL")
    print(f"{'='*60}")
    print(f"  SMILES validity  ≥ {VALIDITY_TARGET:.0%}  → {'PASS' if validity >= VALIDITY_TARGET else 'FAIL'} ({validity:.1%})")
    print(f"  Avg QED          ≥ {QED_TARGET:.2f}  → {'PASS' if avg_qed  >= QED_TARGET  else 'FAIL'} ({avg_qed:.3f})")
    print(f"  Uniqueness       ≥ {UNIQUE_TARGET:.0%}  → {'PASS' if unique   >= UNIQUE_TARGET else 'FAIL'} ({unique:.1%})")
    print(f"  Avg SAS          ≤ {SAS_TARGET:.1f}   → {'PASS' if avg_sas  <= SAS_TARGET  else 'FAIL'} ({avg_sas:.2f})")
    print(f"  Rationale format ≥ 80%  → {'PASS' if rat_rate >= 0.80 else 'FAIL'} ({rat_rate:.1%})")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lora-path", default=OUTPUT_DIR)
    parser.add_argument("--n-prompts", type=int, default=20)
    args = parser.parse_args()
    run_eval(args.lora_path, args.n_prompts)
