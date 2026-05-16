"""
Fine-tune Gemma4-E2B v3 on Deep2Lead drug discovery dataset.

v3 upgrades over v2:
  - Dataset: ~220K records (was 12K) — BindingDB + ChEMBL + Mol-Instructions
  - LoRA r=64, alpha=128 (was r=32, alpha=64)
  - Full 16-bit training (GB10 has 122GB VRAM — no need for 4-bit)
  - Larger effective batch (batch=8, grad_accum=16 → effective=128)
  - 2 epochs (sufficient with 10x more data)
  - Port 9004 (v2 stays on 9003)

Usage:
  python3 train/finetune_gemma4_v3.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_NAME       = "unsloth/gemma-4-E2B-it-unsloth-bnb-4bit"
DATASET_PATH     = "./data/merged_finetune_v3.jsonl"
OUTPUT_DIR       = "./drug_discovery/lora/gemma4_e2b_drug_v3"
MERGED_DIR       = "./drug_discovery/lora/gemma4_e2b_drug_v3_merged"

MAX_SEQ_LENGTH   = 4096
LOAD_IN_4BIT     = False    # Use 16-bit on GB10 — better quality, plenty of VRAM

LORA_R           = 64       # doubled from v2
LORA_ALPHA       = 128      # doubled from v2
LORA_DROPOUT     = 0
USE_RSLORA       = True
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

BATCH_SIZE       = 8        # larger batch (was 4 in v2)
GRAD_ACCUM       = 16       # effective batch = 128
NUM_EPOCHS       = 2        # sufficient with 10x more data
LEARNING_RATE    = 1e-4     # lower LR for larger batch
LR_SCHEDULER     = "cosine"
WARMUP_RATIO     = 0.03
WEIGHT_DECAY     = 0.01
SEED             = 42


def load_dataset(path: str):
    from data.dataset_utils import apply_processor_template
    records = []
    with open(path) as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    print(f"  Loaded {len(records):,} records from {path}")
    return records


def main():
    print(f"\n{'='*60}")
    print(f"Deep2Lead Gemma4-E2B v3 Fine-tuning")
    print(f"  Dataset:  {DATASET_PATH}")
    print(f"  Output:   {OUTPUT_DIR}")
    print(f"  LoRA r:   {LORA_R}  alpha: {LORA_ALPHA}  RSLoRA: {USE_RSLORA}")
    print(f"  Batch:    {BATCH_SIZE} × grad_accum {GRAD_ACCUM} = {BATCH_SIZE*GRAD_ACCUM} effective")
    print(f"  Epochs:   {NUM_EPOCHS}")
    print(f"{'='*60}\n")

    if not os.path.exists(DATASET_PATH):
        print(f"ERROR: Dataset not found: {DATASET_PATH}")
        print("Run: python3 data/build_dataset_v3.py")
        sys.exit(1)

    # ── Load model ──────────────────────────────────────────────────────────
    print("[1/5] Loading model ...")
    from unsloth import FastModel
    import torch

    model, processor = FastModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=LOAD_IN_4BIT,
        dtype=torch.bfloat16,
    )

    # ── Apply LoRA ──────────────────────────────────────────────────────────
    print("[2/5] Applying LoRA ...")
    model = FastModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=LORA_TARGET_MODULES,
        use_rslora=USE_RSLORA,
        bias="none",
    )
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Trainable parameters: {total_params/1e6:.1f}M")

    # ── Prepare dataset ─────────────────────────────────────────────────────
    print("[3/5] Preparing dataset ...")
    from data.dataset_utils import apply_processor_template
    from datasets import Dataset

    raw = load_dataset(DATASET_PATH)

    def tokenize(sample):
        text = apply_processor_template(processor, sample)
        return processor(text, truncation=True, max_length=MAX_SEQ_LENGTH)

    hf_dataset = Dataset.from_list(raw)
    total_steps = (len(raw) // (BATCH_SIZE * GRAD_ACCUM)) * NUM_EPOCHS
    warmup_steps = max(1, int(total_steps * WARMUP_RATIO))
    print(f"  Dataset size:  {len(raw):,}")
    print(f"  Total steps:   {total_steps:,}")
    print(f"  Warmup steps:  {warmup_steps:,}")

    # ── Trainer ─────────────────────────────────────────────────────────────
    print("[4/5] Setting up trainer ...")
    from trl import SFTTrainer, SFTConfig

    sft_config = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        lr_scheduler_type=LR_SCHEDULER,
        warmup_steps=warmup_steps,
        weight_decay=WEIGHT_DECAY,
        seed=SEED,
        logging_steps=50,
        save_steps=500,
        save_total_limit=2,
        bf16=True,
        fp16=False,
        optim="adamw_8bit",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_text_field=None,
        dataset_num_proc=4,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=processor,
        train_dataset=hf_dataset,
        args=sft_config,
        formatting_func=lambda s: apply_processor_template(processor, s),
    )

    # ── Train ────────────────────────────────────────────────────────────────
    print(f"[5/5] Training ...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"\n  Training complete in {elapsed/3600:.1f} hours")

    # ── Save ─────────────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)
    print(f"  LoRA adapter saved → {OUTPUT_DIR}")

    # Save merged model for serve
    print("  Saving merged model ...")
    try:
        model.save_pretrained_merged(MERGED_DIR, processor, save_method="merged_16bit")
        print(f"  Merged model saved → {MERGED_DIR}")
    except Exception as e:
        print(f"  Merged save skipped: {e}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"V3 TRAINING COMPLETE")
    print(f"  Adapter:  {OUTPUT_DIR}")
    print(f"  Merged:   {MERGED_DIR}")
    print(f"  Elapsed:  {elapsed/3600:.1f}h")
    print(f"\nNext: python3 eval/run_full_eval.py --lora-path {OUTPUT_DIR} --output-dir ./eval_results_v3")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
