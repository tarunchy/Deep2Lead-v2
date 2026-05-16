"""
Fine-tune Gemma4-E2B v3 on Deep2Lead drug discovery dataset.

v3 upgrades over v2:
  - Dataset: ~225K records — BindingDB + ChEMBL + MOSES + Custom
  - LoRA r=64, alpha=128 with RS-LoRA (was r=32, alpha=64)
  - 4-bit base load + bf16 LoRA (unsloth bnb-4bit model)
  - Effective batch=128 (batch=8 x grad_accum=16)
  - 2 epochs, LR=1e-4 cosine
  - Port 9004 (v2 stays on 9003)
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

MODEL_NAME   = "unsloth/gemma-4-E2B-it-unsloth-bnb-4bit"
DATASET_PATH = "./data/merged_finetune_v3.jsonl"
OUTPUT_DIR   = "./drug_discovery/lora/gemma4_e2b_drug_v3"
MERGED_DIR   = "./drug_discovery/lora/gemma4_e2b_drug_v3_merged"

MAX_SEQ_LENGTH = 4096
LOAD_IN_4BIT   = True

LORA_R       = 64
LORA_ALPHA   = 128
LORA_DROPOUT = 0
USE_RSLORA   = True
LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj"]

BATCH_SIZE   = 8
GRAD_ACCUM   = 16
NUM_EPOCHS   = 2
LR           = 1e-4
LR_SCHED     = "cosine"
WARMUP_RATIO = 0.03
WEIGHT_DECAY = 0.01
SEED         = 42


def main():
    print(f"\n{'='*60}")
    print(f"Deep2Lead Gemma4-E2B v3 Fine-tuning")
    print(f"  Dataset : {DATASET_PATH}")
    print(f"  Output  : {OUTPUT_DIR}")
    print(f"  LoRA    : r={LORA_R} alpha={LORA_ALPHA} RSLoRA={USE_RSLORA}")
    print(f"  Batch   : {BATCH_SIZE} x {GRAD_ACCUM} = {BATCH_SIZE*GRAD_ACCUM} effective")
    print(f"  Epochs  : {NUM_EPOCHS}  LR={LR}")
    print(f"{'='*60}\n")

    if not os.path.exists(DATASET_PATH):
        sys.exit(f"ERROR: Dataset not found: {DATASET_PATH}")

    # ── [1] Load model ────────────────────────────────────────────────────────
    print("[1/5] Loading model ...")
    from unsloth import FastModel
    model, processor = FastModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=LOAD_IN_4BIT,
    )

    # ── [2] LoRA ──────────────────────────────────────────────────────────────
    print("[2/5] Applying LoRA ...")
    model = FastModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=LORA_TARGETS,
        use_rslora=USE_RSLORA,
        bias="none",
    )
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Trainable params: {trainable/1e6:.1f}M")

    # ── [3] Dataset ──────────────────────────────────────────────────────────
    print("[3/5] Preparing dataset ...")
    records = []
    with open(DATASET_PATH) as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    print(f"  Loaded {len(records):,} records")

    # Pre-apply chat template to produce plain text strings
    print("  Applying chat template ...")
    texts = []
    for r in records:
        try:
            t = processor.apply_chat_template(
                r["messages"], tokenize=False, add_generation_prompt=False
            )
            texts.append(t)
        except Exception:
            pass
    print(f"  Templated {len(texts):,} records")

    from datasets import Dataset
    hf_dataset = Dataset.from_dict({"text": texts})

    total_steps  = (len(texts) // (BATCH_SIZE * GRAD_ACCUM)) * NUM_EPOCHS
    warmup_steps = max(1, int(total_steps * WARMUP_RATIO))
    print(f"  Total steps : {total_steps:,}  Warmup: {warmup_steps}")

    # ── [4] Trainer ──────────────────────────────────────────────────────────
    print("[4/5] Setting up trainer ...")
    from trl import SFTTrainer, SFTConfig

    sft_config = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LR,
        lr_scheduler_type=LR_SCHED,
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
        dataset_text_field="text",
        dataset_num_proc=4,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=processor,
        train_dataset=hf_dataset,
        args=sft_config,
    )

    # ── [5] Train ─────────────────────────────────────────────────────────────
    print("[5/5] Training — this runs overnight ...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"\n  Done in {elapsed/3600:.2f}h")

    # ── Save ──────────────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)
    print(f"  LoRA adapter → {OUTPUT_DIR}")

    try:
        model.save_pretrained_merged(MERGED_DIR, processor, save_method="merged_16bit")
        print(f"  Merged model → {MERGED_DIR}")
    except Exception as e:
        print(f"  Merged save skipped: {e}")

    print(f"\n{'='*60}")
    print(f"V3 TRAINING COMPLETE  ({elapsed/3600:.2f}h)")
    print(f"  Adapter : {OUTPUT_DIR}")
    print(f"  Merged  : {MERGED_DIR}")
    print(f"  Next    : python3 eval/run_full_eval.py --lora-path {OUTPUT_DIR} --output-dir ./eval_results_v3")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
