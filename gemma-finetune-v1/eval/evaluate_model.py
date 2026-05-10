#!/usr/bin/env python3
"""
Evaluate the fine-tuned Gemma4-E2B model on drug discovery tasks.
Runs on DGX after training completes.

Usage:
    python3 eval/evaluate_model.py [--lora-path ./drug_discovery/lora/gemma4_e2b_drug_v1]
                                   [--n-prompts 50]

Metrics:
    - SMILES validity %
    - Average QED (drug-likeness)
    - Average SAS (synthetic accessibility)
    - Unique SMILES %
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import MODEL_NAME, MAX_SEQ_LENGTH, OUTPUT_DIR, TARGETS_JSON_PATH
from data.dataset_utils import is_valid_smiles, drug_like_filter, SYSTEM_PROMPT


EVAL_PROMPTS = [
    "Generate 5 novel drug-like SMILES that inhibit SARS-CoV-2 Main Protease. MW 250-450, QED>0.5.",
    "Generate 5 SMILES for potential HIV-1 Protease inhibitors. Keep MW under 500 and QED above 0.4.",
    "Generate 5 diverse drug-like molecules with LogP between 1 and 4, MW 200-400.",
    "Generate 3 novel antiviral SMILES inspired by Oseltamivir: CCOC(=O)[C@@H]1CC(=C[C@@H](O1)OC(CC)CC)NC(C)=O",
    "Generate 5 SMILES for kinase inhibitor candidates with an aromatic scaffold.",
    "Generate 4 SMILES for CDK2 inhibitors. Consider purine or pyrimidine scaffolds.",
    "Generate 3 Bcl-2 inhibitor SMILES with hydrophobic regions for BH3 groove binding.",
    "Generate 5 novel molecules similar to Imatinib but with improved MW < 480.",
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


def run_eval(lora_path: str, n_prompts: int):
    print(f"\nLoading fine-tuned model...")
    print(f"  Base:  {MODEL_NAME}")
    print(f"  LoRA:  {lora_path}\n")

    from unsloth import FastModel

    model, processor = FastModel.from_pretrained(
        model_name=lora_path,   # load from saved adapter (unsloth auto-detects base)
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=True,
        dtype=None,
    )
    FastModel.for_inference(model)

    prompts = (EVAL_PROMPTS * 10)[:n_prompts]
    all_smiles = []
    results_per_prompt = []

    for i, prompt in enumerate(prompts):
        print(f"[{i+1}/{n_prompts}] {prompt[:70]}...")
        messages = [
            {"role": "system",    "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
            {"role": "user",      "content": [{"type": "text", "text": prompt}]},
        ]
        inputs = processor.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt",
            return_dict=True, tokenize=True,
        ).to("cuda")

        import torch
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=True,
                temperature=0.8,
                top_p=0.9,
            )

        generated = outputs[0][inputs["input_ids"].shape[-1]:]
        response  = processor.decode(generated, skip_special_tokens=True).strip()

        # Extract SMILES from response
        from data.dataset_utils import extract_smiles_from_text
        smiles_in_response = extract_smiles_from_text(response)
        all_smiles.extend(smiles_in_response)
        results_per_prompt.append({
            "prompt":   prompt,
            "response": response,
            "smiles":   smiles_in_response,
        })

    # Aggregate metrics
    print(f"\n{'='*60}")
    print(f"EVALUATION RESULTS ({n_prompts} prompts, {len(all_smiles)} extracted SMILES)")
    print(f"{'='*60}")
    metrics = compute_rdkit_metrics(all_smiles)
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:<20} {v:.3f}")
        else:
            print(f"  {k:<20} {v}")

    # Save results
    out_path = os.path.join(os.path.dirname(lora_path), "eval_results.json")
    with open(out_path, "w") as f:
        json.dump({"metrics": metrics, "per_prompt": results_per_prompt}, f, indent=2)
    print(f"\nFull results saved → {out_path}")

    # Pass/fail vs targets
    print(f"\n{'='*60}")
    validity = metrics.get("validity", 0)
    avg_qed  = metrics.get("avg_qed", 0)
    print(f"Target: validity ≥ 0.90  →  {'PASS' if validity >= 0.90 else 'FAIL'} ({validity:.1%})")
    print(f"Target: avg QED  ≥ 0.45  →  {'PASS' if avg_qed  >= 0.45 else 'FAIL'} ({avg_qed:.3f})")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lora-path", default=OUTPUT_DIR)
    parser.add_argument("--n-prompts", type=int, default=20)
    args = parser.parse_args()
    run_eval(args.lora_path, args.n_prompts)
