"""
Full three-tier evaluation for Deep2Lead Gemma4-E2B v2.

Usage:
    python3 eval/run_full_eval.py \
        --lora-path ./drug_discovery/lora/gemma4_e2b_drug_v2 \
        --merged-data ./data/merged_finetune_v2.jsonl \
        --n-general 60 \
        --n-per-target 20 \
        [--skip-mammal]        # run without dlyog03 API (Tier 2 scores omitted)
        [--output-dir ./eval_results]

Outputs (in --output-dir):
    tier1_chemistry.json
    tier2_target_cond.json
    tier3_rationale.json
    summary_table.md          ← paper-ready markdown tables
    full_results.json         ← everything merged
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── General prompts for Tier 1 + 3 (diverse, not target-specific) ─────────────

GENERAL_PROMPTS = [
    # Target-conditioned
    "Target: SARS-CoV-2 Nsp5 Main Protease\n"
    "Protein (120AA): SGFRKMAFPSGKVEGCMVQVTCGTTTLNGLWLDDVVYCPRHVICTSEDMLNPNYEDLLIRKSNHNFLV\n"
    "Design 4 protease inhibitors, MW 300-500, QED>0.55. Rationale first.",

    "Target: EGFR T790M (gatekeeper mutant), lung cancer.\n"
    "Protein (120AA): MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEVVLGNLEITYV\n"
    "Generate 4 covalent or 3rd-gen inhibitor SMILES. Explain T790M workaround strategy first.",

    "Target: CDK2/Cyclin E, cancer cell cycle.\n"
    "Protein (120AA): MENFQKVEKIGEGTYGVVYKARNKLTGEVVALKKIRLDTETEGVPSTAIREISLLKELNHPNIVKLL\n"
    "Design 3 selective ATP-competitive inhibitors. Structural reasoning first.",

    "Target: DPP-4 (type 2 diabetes), catalytic Ser630-Asp708-His740 triad.\n"
    "Protein (120AA): MKTPWKVLLGLLGAAALVTIITVPVVLLNKGTDDATADSRKTYTLTNKNVFEGQTLDATLYHYQMN\n"
    "Design 4 competitive inhibitors. Rationale about pharmacophore before SMILES.",

    "Target: BACE1 (Alzheimer's aspartyl protease).\n"
    "Protein (120AA): MAQALPWLLLWMGAGVLPAHGTQHGIRLPLRSGLGGAPLGLRLPRETDEEPEEPGRRGSFVEMVDN\n"
    "Generate 3 CNS-penetrant inhibitors: MW<450, PSA<90. BBB reasoning first.",

    # Scaffold hop
    "Erlotinib SMILES: C#Cc1cccc(c1)Nc2ncnc3cc(OCC)c(OCC)cc23\n"
    "Perform a scaffold hop: design 3 SMILES with different core ring system but preserved pharmacophore. "
    "Explain your bioisostere strategy before providing SMILES.",

    "Imatinib SMILES: Cc1ccc(cc1Nc2nccc(n2)c3cccnc3)NC(=O)c4ccc(cc4)CN5CCN(CC5)C\n"
    "Design 2 structurally distinct BCR-ABL inhibitor scaffolds avoiding this core. "
    "Rationale first, then SMILES.",

    "Aspirin SMILES: CC(=O)Oc1ccccc1C(=O)O\n"
    "Generate 4 bioisosteric analogs of aspirin with improved COX-2 selectivity. "
    "Explain the selectivity design strategy, then SMILES.",

    # Property-conditioned
    "Generate 5 drug-like SMILES with MW 350-400 Da, LogP 2.0-3.5, QED > 0.65, "
    "at least one H-bond donor, passes Lipinski Ro5. Explain design strategy first.",

    "Design 4 CNS-penetrant molecules: MW < 420, LogP 1-3, PSA < 90, max 1 HBD. "
    "Explain BBB permeability criteria before providing SMILES.",

    "Generate 3 fragment-like molecules: MW 150-300, HAC ≤ 25, at least 1 ring. "
    "Explain fragment-based drug discovery strategy, then SMILES.",

    "Design 4 PROTAC-compatible ligands: MW 200-350, includes amine or carboxylic acid "
    "for linker attachment. Explain warhead strategy, then SMILES.",

    # Mechanism-based
    "Generate 4 kinase inhibitor SMILES with an aromatic hinge-binding scaffold. "
    "Explain hinge hydrogen-bond geometry first.",

    "Design 3 HDAC inhibitor SMILES using a hydroxamic acid zinc-binding group. "
    "Explain chelation strategy before SMILES.",

    "Generate 4 allosteric inhibitor candidates for a protein kinase. "
    "Explain why allosteric vs ATP-competitive, then SMILES.",

    "Design 3 covalent inhibitors targeting a cysteine residue. "
    "Explain warhead selection (acrylamide vs chloroacetamide) rationale first.",

    # Multi-property optimization
    "Design a dual inhibitor targeting both EGFR and VEGFR-2 with MW < 500 and QED > 0.6. "
    "Explain multi-target pharmacophore design, then provide 3 SMILES.",

    "Generate 4 molecules combining a kinase hinge binder with a solubilizing morpholine. "
    "Rationale about lipophilicity balance first.",

    "Design 3 prodrug candidates for a hydrophilic active compound (like gemcitabine). "
    "Explain pro-moiety strategy for oral bioavailability, then SMILES.",

    "Generate 5 diverse scaffolds for a PPI (protein-protein interaction) inhibitor. "
    "Explain why flat aromatic scaffolds help with PPI binding, then SMILES.",
]


def _load_model(lora_path: str, max_seq_length: int):
    from unsloth import FastModel
    model, processor = FastModel.from_pretrained(
        model_name=lora_path,
        max_seq_length=max_seq_length,
        load_in_4bit=True,
        dtype=None,
    )
    FastModel.for_inference(model)
    return model, processor


def _generate(model, processor, prompt: str, device: str = "cuda") -> str:
    import torch
    from data.dataset_utils import SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
        {"role": "user",   "content": [{"type": "text", "text": prompt}]},
    ]
    inputs = processor.apply_chat_template(
        messages, add_generation_prompt=True,
        return_tensors="pt", return_dict=True, tokenize=True,
    ).to(device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs, max_new_tokens=512,
            do_sample=True, temperature=0.88, top_p=0.92,
            top_k=50, repetition_penalty=1.2,
        )
    ids = outputs[0][inputs["input_ids"].shape[-1]:]
    return processor.decode(ids, skip_special_tokens=True).strip()


def _build_summary_md(t1: dict, t2: list[dict], t3: dict, label: str) -> str:
    from eval.eval_utils import fmt_table
    lines = [f"# Deep2Lead Evaluation Report — {label}", ""]

    lines += [
        "## Table 1 — Chemical Quality (Tier 1)",
        "",
        fmt_table([{
            "Metric": "SMILES Validity",     "Value": f"{t1.get('validity', 0):.1%}",   "Target": "≥ 95%"},
        ], ["Metric", "Value", "Target"]),
    ]
    # Full T1 table
    t1_rows = [
        {"Metric": "SMILES Validity",     "Value": f"{t1.get('validity',0):.1%}",        "Target": "≥ 95%"},
        {"Metric": "Uniqueness",          "Value": f"{t1.get('uniqueness',0):.1%}",       "Target": "≥ 90%"},
        {"Metric": "Novelty (Tc < 0.4)",  "Value": f"{t1.get('novelty',0):.1%}",         "Target": "≥ 80%"},
        {"Metric": "Internal Diversity",  "Value": f"{t1.get('internal_diversity',0):.3f}","Target": "> 0.70"},
        {"Metric": "Lipinski Ro5",        "Value": f"{t1.get('ro5_pass_rate',0):.1%}",   "Target": "≥ 85%"},
        {"Metric": "Avg QED",             "Value": f"{t1.get('avg_qed',0):.3f} ± {t1.get('std_qed',0):.3f}", "Target": "≥ 0.60"},
        {"Metric": "Avg SAS",             "Value": f"{t1.get('avg_sas',0):.3f} ± {t1.get('std_sas',0):.3f}", "Target": "≤ 4.5"},
        {"Metric": "Avg MW (Da)",         "Value": f"{t1.get('avg_mw',0):.1f}",           "Target": "200–500"},
        {"Metric": "Avg LogP",            "Value": f"{t1.get('avg_logp',0):.3f}",         "Target": "0–5"},
    ]
    lines = [f"# Deep2Lead Evaluation Report — {label}", ""]
    lines += ["## Table 1 — Chemical Quality (Tier 1)", ""]
    lines.append("| Metric | Value | Target |")
    lines.append("| --- | --- | --- |")
    for row in t1_rows:
        lines.append(f"| {row['Metric']} | {row['Value']} | {row['Target']} |")
    lines.append("")

    # T2 table
    if t2:
        lines += ["## Table 2 — Target-Conditioned Generation (Tier 2)", ""]
        lines.append("| Target | Disease | N | Scaffolds | mean pKd | % Binder | Δ Known |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for r in t2:
            mean_pkd   = f"{r['mean_pkd']:.3f}" if "mean_pkd" in r else "N/A"
            pct_binder = f"{r['pct_binder']:.1%}" if "pct_binder" in r else "N/A"
            delta      = f"{r['delta_pkd_vs_known']:+.3f}" if "delta_pkd_vs_known" in r else "N/A"
            lines.append(
                f"| {r['target_name']} | {r['disease']} | {r['n_generated']} "
                f"| {r['n_scaffolds']} | {mean_pkd} | {pct_binder} | {delta} |"
            )
        lines.append("")

    # T3 table
    if t3:
        lines += ["## Table 3 — Rationale Quality (Tier 3)", ""]
        t3_rows = [
            ("Format compliance",   f"{t3.get('rationale_format_rate', 0):.1%}",   "≥ 90%"),
            ("Keyword coverage",    f"{t3.get('keyword_coverage_rate', 0):.1%}",    "≥ 70%"),
            ("Coherence score",     f"{t3.get('coherence_score', 0):.3f}",          "> 0.60"),
            ("Composite score",     f"{t3.get('composite_score', 0):.3f}",          "> 0.65"),
        ]
        if "rationale_pkd_correlation" in t3:
            t3_rows.append(("Rationale–pKd r", f"{t3['rationale_pkd_correlation']:.3f}", "> 0"))
        lines.append("| Metric | Value | Target |")
        lines.append("| --- | --- | --- |")
        for m, v, tgt in t3_rows:
            lines.append(f"| {m} | {v} | {tgt} |")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lora-path",    default="./drug_discovery/lora/gemma4_e2b_drug_v2")
    parser.add_argument("--merged-data",  default="./data/merged_finetune_v2.jsonl")
    parser.add_argument("--n-general",    type=int, default=60,  help="Prompts for Tier 1 + 3")
    parser.add_argument("--n-per-target", type=int, default=20,  help="SMILES per target for Tier 2")
    parser.add_argument("--skip-mammal",  action="store_true")
    parser.add_argument("--output-dir",   default="./eval_results")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    label = os.path.basename(args.lora_path.rstrip("/"))

    from config import MODEL_NAME, MAX_SEQ_LENGTH

    print(f"\n{'='*60}")
    print(f" Deep2Lead Full Evaluation — {label}")
    print(f" Model:      {MODEL_NAME}")
    print(f" LoRA path:  {args.lora_path}")
    print(f"{'='*60}\n")

    # ── Load model ──────────────────────────────────────────────────────────────
    print("[Loading model] ...")
    t0 = time.time()
    model, processor = _load_model(args.lora_path, MAX_SEQ_LENGTH)
    print(f"  Loaded in {time.time()-t0:.1f}s\n")

    # ── Load training SMILES for novelty ────────────────────────────────────────
    from eval.tier1_chemistry import load_training_smiles
    print("[Loading training SMILES for novelty baseline] ...")
    train_smiles = load_training_smiles(args.merged_data)
    print(f"  {len(train_smiles):,} training SMILES loaded\n")

    # ── Generate responses for Tier 1 + 3 ──────────────────────────────────────
    from eval.eval_utils import extract_smiles_from_text
    prompts = (GENERAL_PROMPTS * 10)[:args.n_general]
    all_smiles:    list[str] = []
    all_responses: list[str] = []

    print(f"[Generating {len(prompts)} responses for Tier 1 + 3] ...")
    for i, prompt in enumerate(prompts, 1):
        print(f"  [{i}/{len(prompts)}] {prompt[:70].strip()}...")
        response = _generate(model, processor, prompt)
        smiles   = extract_smiles_from_text(response)
        all_smiles.extend(smiles)
        all_responses.append(response)
        print(f"    → {len(smiles)} SMILES | {'Rationale: ✓' if 'rationale:' in response.lower() else 'Rationale: ✗'}")

    print(f"\n  Total SMILES extracted: {len(all_smiles)}")

    # ── Tier 1 ──────────────────────────────────────────────────────────────────
    print("\n[Tier 1 — Chemical quality] ...")
    from eval.tier1_chemistry import run_tier1, print_tier1
    t1 = run_tier1(all_smiles, train_smiles, label=label)
    print_tier1(t1)
    with open(os.path.join(args.output_dir, "tier1_chemistry.json"), "w") as f:
        json.dump(t1, f, indent=2)

    # ── Tier 2 ──────────────────────────────────────────────────────────────────
    print("\n[Tier 2 — Target-conditioned generation + MAMMAL scoring] ...")
    from eval.tier2_target_cond import run_tier2, print_tier2
    t2 = run_tier2(model, processor, n_per_target=args.n_per_target,
                   skip_mammal=args.skip_mammal)
    print_tier2(t2)
    # Remove tensor data before JSON serialization
    t2_serializable = []
    for r in t2:
        r2 = {k: v for k, v in r.items() if k not in ("gen_mammal", "known_mammal")}
        r2["gen_mammal"]   = r.get("gen_mammal", [])
        r2["known_mammal"] = r.get("known_mammal", [])
        t2_serializable.append(r2)
    with open(os.path.join(args.output_dir, "tier2_target_cond.json"), "w") as f:
        json.dump(t2_serializable, f, indent=2)

    # ── Tier 3 ──────────────────────────────────────────────────────────────────
    print("\n[Tier 3 — Rationale quality] ...")
    from eval.tier3_rationale import run_tier3, print_tier3

    # Collect pKd scores from Tier 2 results aligned with responses if possible
    # For Tier 1 responses we don't have per-response pKd, so pass None
    t3 = run_tier3(all_responses, pkds=None)
    print_tier3(t3)
    t3_out = {k: v for k, v in t3.items() if k != "per_response"}
    t3_out["per_response_sample"] = t3.get("per_response", [])[:5]
    with open(os.path.join(args.output_dir, "tier3_rationale.json"), "w") as f:
        json.dump(t3_out, f, indent=2)

    # ── Summary markdown ────────────────────────────────────────────────────────
    print("\n[Building summary tables] ...")
    md = _build_summary_md(t1, t2, t3, label)
    md_path = os.path.join(args.output_dir, "summary_table.md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"  Saved: {md_path}")

    # ── Full JSON dump ──────────────────────────────────────────────────────────
    full = {"label": label, "tier1": t1, "tier2": t2_serializable, "tier3": t3_out}
    full_path = os.path.join(args.output_dir, "full_results.json")
    with open(full_path, "w") as f:
        json.dump(full, f, indent=2)
    print(f"  Saved: {full_path}")

    # ── Final verdict ───────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f" EVALUATION COMPLETE — {label}")
    print(f"{'='*60}")
    print(f"  Tier 1 validity:   {t1.get('validity', 0):.1%}")
    print(f"  Tier 1 QED:        {t1.get('avg_qed', 0):.3f}")
    print(f"  Tier 3 rationale:  {t3.get('rationale_format_rate', 0):.1%} format "
          f"| {t3.get('composite_score', 0):.3f} composite")
    if t2:
        pkds = [r.get("mean_pkd") for r in t2 if "mean_pkd" in r]
        if pkds:
            import statistics
            print(f"  Tier 2 avg pKd:    {statistics.mean(pkds):.3f} across {len(pkds)} targets")
    print(f"\n  Results → {args.output_dir}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
