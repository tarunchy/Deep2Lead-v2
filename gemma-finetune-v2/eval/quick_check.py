"""
Quick sanity check on a checkpoint — 3 sample generations.
Run alongside training: loads in 4-bit, minimal GPU impact.

Usage:
    python3 eval/quick_check.py \
        --checkpoint ./drug_discovery/lora/gemma4_e2b_drug_v3/checkpoint-1000
"""
import argparse, re, sys
from rdkit import Chem
from rdkit.Chem import QED

PROMPTS = [
    ("SARS-CoV-2 MPro",
     "SGFRKMAFPSGKVEGCMVQVTCGTTTLNGLWLDDVVYCPRHVICTSEDMLNPNYEDLLIRK"),
    ("EGFR Kinase",
     "MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEV"),
    ("BACE1 Alzheimer's",
     "MAQALPWLLLWMGAGVLPAHGTQHGIRLPLRSGLGGAPLLLLQALLGDPSTPAASGASGE"),
]

def check_smiles(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return False, 0.0
    return True, round(QED.qed(mol), 3)

def extract_smiles(text):
    m = re.search(r'\*\*SMILES:\*\*\s*([^\n]+)', text)
    if m:
        return m.group(1).strip()
    m = re.search(r'SMILES:\s*([A-Za-z0-9@\[\]()=#\-\+\.\/\\%]+)', text)
    if m:
        return m.group(1).strip()
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"Quick check: {args.checkpoint}")
    print(f"{'='*60}\n")

    from unsloth import FastLanguageModel
    model, tokenizer = FastLanguageModel.from_pretrained(
        args.checkpoint,
        load_in_4bit=True,
        max_seq_length=1024,
    )
    FastLanguageModel.for_inference(model)

    results = []
    for target, seq in PROMPTS:
        prompt = (
            f"<start_of_turn>user\n"
            f"Target: {target}\nProtein (60AA): {seq}\n"
            f"Generate a drug candidate. Rationale first, then SMILES.\n"
            f"<end_of_turn>\n<start_of_turn>model\n"
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        out = model.generate(**inputs, max_new_tokens=300, temperature=0.7,
                             do_sample=True, pad_token_id=tokenizer.eos_token_id)
        response = tokenizer.decode(out[0][inputs.input_ids.shape[1]:],
                                    skip_special_tokens=True)

        smiles = extract_smiles(response)
        valid, qed = check_smiles(smiles) if smiles else (False, 0.0)

        status = "✓ VALID" if valid else "✗ INVALID"
        print(f"Target:  {target}")
        print(f"SMILES:  {smiles or 'NOT FOUND'}")
        print(f"Status:  {status}  |  QED: {qed}")
        print(f"Preview: {response[:120].strip()}...")
        print()
        results.append({"target": target, "valid": valid, "qed": qed})

    valid_count = sum(r["valid"] for r in results)
    avg_qed = sum(r["qed"] for r in results) / len(results)

    print(f"{'='*60}")
    print(f"SMILES validity: {valid_count}/{len(results)}")
    print(f"Average QED:     {avg_qed:.3f}  (target: >0.5)")
    print(f"Checkpoint looks {'GOOD ✓' if valid_count >= 2 else 'CONCERNING ⚠'}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
