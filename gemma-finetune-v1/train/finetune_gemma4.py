#!/usr/bin/env python3
"""
Gemma4-E2B Drug Discovery Fine-Tuning Script
Run on DGX1: source ~/unsloth/.unsloth/bin/activate && python3 train/finetune_gemma4.py

Hardware: NVIDIA GB10 (Grace Blackwell), 128GB unified memory
Model:    unsloth/gemma-4-E2B-it-unsloth-bnb-4bit (text-only fine-tuning)
Dataset:  SMolInstruct (filtered) + Deep2Lead custom instructions
Output:   LoRA adapter + merged 16-bit model + GGUF for Mac
"""

import os
import sys
import json
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (
    MODEL_NAME, MAX_SEQ_LENGTH, LOAD_IN_4BIT,
    LORA_R, LORA_ALPHA, LORA_DROPOUT, LORA_TARGET_MODULES,
    BATCH_SIZE, GRAD_ACCUM, NUM_EPOCHS, LEARNING_RATE,
    LR_SCHEDULER, WARMUP_RATIO, WEIGHT_DECAY, SEED,
    OUTPUT_DIR, MERGED_DIR, GGUF_DIR, GGUF_QUANT,
    MERGED_DATASET_PATH, CUSTOM_DATASET_PATH,
)

# ── 1. Load model ──────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"Loading {MODEL_NAME}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM total: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print(f"VRAM free:  {torch.cuda.mem_get_info()[0] / 1e9:.1f} GB")
print(f"{'='*60}\n")

from unsloth import FastModel

model, processor = FastModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    load_in_4bit=LOAD_IN_4BIT,
    dtype=None,           # auto bf16 on GB10 Blackwell
    full_finetuning=False,
)

# ── 2. Apply LoRA ──────────────────────────────────────────────────────────────
print("Applying LoRA adapters...")
model = FastModel.get_peft_model(
    model,
    r=LORA_R,
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    target_modules=LORA_TARGET_MODULES,
    use_gradient_checkpointing="unsloth",
    random_state=SEED,
    use_rslora=False,
)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total     = sum(p.numel() for p in model.parameters())
print(f"Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

# ── 3. Load dataset ────────────────────────────────────────────────────────────

def _load_jsonl(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def _format_record(sample: dict) -> dict:
    """Convert a messages-list record to a flat 'text' field for SFTTrainer."""
    messages = sample.get("messages", [])
    text = processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    return {"text": text}


print("\nLoading training dataset...")
merged_records = _load_jsonl(MERGED_DATASET_PATH)
custom_records = _load_jsonl(CUSTOM_DATASET_PATH)

if not merged_records and not custom_records:
    print("ERROR: No dataset found. Run these first:")
    print("  python3 data/download_datasets.py")
    print("  python3 data/build_custom_dataset.py")
    sys.exit(1)

all_records = merged_records + custom_records
print(f"  SMolInstruct+MOSES: {len(merged_records):,}")
print(f"  Deep2Lead custom:   {len(custom_records):,}")
print(f"  Total:              {len(all_records):,}")

from datasets import Dataset
import random

random.seed(SEED)
random.shuffle(all_records)

raw_dataset = Dataset.from_list(all_records)
print("Applying Gemma4 chat template to dataset...")
dataset = raw_dataset.map(_format_record, batched=False, num_proc=4, desc="Formatting")

# Sanity check
print("\n--- Sample formatted record (first 600 chars) ---")
print(dataset[0]["text"][:600])
print("--- end ---\n")

# ── 4. Train ───────────────────────────────────────────────────────────────────
from trl import SFTTrainer, SFTConfig

total_steps  = (len(dataset) * NUM_EPOCHS) // (BATCH_SIZE * GRAD_ACCUM)
warmup_steps = max(5, int(total_steps * WARMUP_RATIO))

print(f"Training config:")
print(f"  Records:       {len(dataset):,}")
print(f"  Epochs:        {NUM_EPOCHS}")
print(f"  Batch:         {BATCH_SIZE} × {GRAD_ACCUM} = {BATCH_SIZE*GRAD_ACCUM} effective")
print(f"  Total steps:   {total_steps}")
print(f"  Warmup steps:  {warmup_steps}")
print(f"  LR:            {LEARNING_RATE}")
print(f"  Output:        {OUTPUT_DIR}\n")

os.makedirs(OUTPUT_DIR, exist_ok=True)

trainer = SFTTrainer(
    model=model,
    tokenizer=processor,
    train_dataset=dataset,
    args=SFTConfig(
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        packing=False,
        dataset_num_proc=4,

        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        warmup_steps=warmup_steps,
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
        lr_scheduler_type=LR_SCHEDULER,

        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),

        logging_steps=20,
        logging_dir=f"{OUTPUT_DIR}/logs",
        save_strategy="epoch",
        save_total_limit=2,
        output_dir=OUTPUT_DIR,
        seed=SEED,

        optim="adamw_8bit",
        report_to="none",
    ),
)

print("Starting training...")
stats = trainer.train()
print(f"\nTraining complete!")
print(f"  Runtime:      {stats.metrics.get('train_runtime', 0):.0f}s")
print(f"  Samples/sec:  {stats.metrics.get('train_samples_per_second', 0):.2f}")
print(f"  Final loss:   {stats.metrics.get('train_loss', 0):.4f}")

# ── 5. Save LoRA adapter ───────────────────────────────────────────────────────
print(f"\nSaving LoRA adapter → {OUTPUT_DIR}")
model.save_pretrained(OUTPUT_DIR)
processor.save_pretrained(OUTPUT_DIR)
print("LoRA adapter saved.")

# ── 6. Export merged model (Kaggle submission needs this) ──────────────────────
print(f"\nExporting merged 16-bit model → {MERGED_DIR}")
print("(Merges LoRA into base weights — required for Kaggle demo)")
os.makedirs(MERGED_DIR, exist_ok=True)
model.save_pretrained_merged(MERGED_DIR, processor, save_method="merged_16bit")
print("Merged model saved.")

# ── 7. Export GGUF for Mac local demo ─────────────────────────────────────────
print(f"\nExporting GGUF ({GGUF_QUANT}) → {GGUF_DIR}")
os.makedirs(GGUF_DIR, exist_ok=True)
model.save_pretrained_gguf(GGUF_DIR, processor, quantization_method=GGUF_QUANT)

from pathlib import Path
for f in Path(GGUF_DIR).glob("*.gguf"):
    size_mb = f.stat().st_size / 1e6
    print(f"  {f.name}  ({size_mb:.0f} MB)")

print("\n" + "="*60)
print("DONE. Next steps:")
print(f"  1. Evaluate:  python3 eval/evaluate_model.py")
print(f"  2. Serve:     python3 serve/serve_finetuned.py  (port 9002)")
print(f"  3. Kaggle:    push {MERGED_DIR}/ to HuggingFace Hub")
print(f"  4. GGUF demo: scp {GGUF_DIR}/*.gguf tarun@mac:~/models/")
print("="*60)
