#!/usr/bin/env python3
"""
Gemma4-E2B Drug Discovery Fine-Tuning Script — v2

Key upgrades over v1:
  - LoRA r=32, alpha=64 with RS-LoRA (rank-stabilized)
  - 65% target-conditioned ChEMBL/BindingDB + MAMMAL-filtered data
  - Rationale-first ChatML training format
  - LR=1.5e-4 with cosine schedule and warmup

Run on DGX1:
    source ~/unsloth/.unsloth/bin/activate
    python3 train/finetune_gemma4_v2.py
"""

import os
import sys
import json
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (
    MODEL_NAME, MAX_SEQ_LENGTH, LOAD_IN_4BIT,
    LORA_R, LORA_ALPHA, LORA_DROPOUT, LORA_TARGET_MODULES, USE_RSLORA,
    BATCH_SIZE, GRAD_ACCUM, NUM_EPOCHS, LEARNING_RATE,
    LR_SCHEDULER, WARMUP_RATIO, WEIGHT_DECAY, SEED,
    OUTPUT_DIR, MERGED_DIR, GGUF_DIR, GGUF_QUANT,
    MERGED_DATASET_PATH, CUSTOM_DATASET_PATH,
)

# ── 1. Load model ──────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"Gemma4-E2B Drug Discovery Fine-tuning v2")
print(f"Loading {MODEL_NAME}")
print(f"CUDA: {torch.cuda.is_available()}")
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
    dtype=None,
    full_finetuning=False,
)

# ── 2. Apply LoRA v2 ───────────────────────────────────────────────────────────
print(f"Applying LoRA v2 (r={LORA_R}, alpha={LORA_ALPHA}, RS-LoRA={USE_RSLORA}) ...")
model = FastModel.get_peft_model(
    model,
    r=LORA_R,
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    target_modules=LORA_TARGET_MODULES,
    use_gradient_checkpointing="unsloth",
    random_state=SEED,
    use_rslora=USE_RSLORA,
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
    messages = sample.get("messages", [])
    text = processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    return {"text": text}


print("\nLoading v2 training dataset ...")
merged_records = _load_jsonl(MERGED_DATASET_PATH)
custom_records = _load_jsonl(CUSTOM_DATASET_PATH)

if not merged_records and not custom_records:
    print("ERROR: No dataset found. Run these steps first:")
    print("  python3 data/build_custom_dataset_v2.py")
    print("  python3 data/download_datasets_v2.py")
    sys.exit(1)

all_records = merged_records + custom_records
print(f"  Merged dataset: {len(merged_records):,}")
print(f"  Custom v2:      {len(custom_records):,}")
print(f"  Total:          {len(all_records):,}")

from datasets import Dataset
import random

random.seed(SEED)
random.shuffle(all_records)

raw_dataset = Dataset.from_list(all_records)
print("Applying Gemma4 chat template ...")
dataset = raw_dataset.map(_format_record, batched=False, num_proc=4, desc="Formatting")

print("\n--- Sample record (first 800 chars) ---")
print(dataset[0]["text"][:800])
print("--- end ---\n")

# ── 4. Train ───────────────────────────────────────────────────────────────────
from trl import SFTTrainer, SFTConfig

total_steps  = (len(dataset) * NUM_EPOCHS) // (BATCH_SIZE * GRAD_ACCUM)
warmup_steps = max(5, int(total_steps * WARMUP_RATIO))

print(f"v2 Training config:")
print(f"  Records:         {len(dataset):,}")
print(f"  Epochs:          {NUM_EPOCHS}")
print(f"  Batch:           {BATCH_SIZE} × {GRAD_ACCUM} = {BATCH_SIZE*GRAD_ACCUM} effective")
print(f"  Total steps:     {total_steps}")
print(f"  Warmup steps:    {warmup_steps}")
print(f"  LR:              {LEARNING_RATE}")
print(f"  LoRA r/alpha:    {LORA_R}/{LORA_ALPHA}  RS-LoRA={USE_RSLORA}")
print(f"  Output:          {OUTPUT_DIR}\n")

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

print("Starting v2 training ...")
stats = trainer.train()
print(f"\nTraining complete!")
print(f"  Runtime:      {stats.metrics.get('train_runtime', 0):.0f}s")
print(f"  Samples/sec:  {stats.metrics.get('train_samples_per_second', 0):.2f}")
print(f"  Final loss:   {stats.metrics.get('train_loss', 0):.4f}")

# ── 5. Save LoRA adapter ───────────────────────────────────────────────────────
print(f"\nSaving v2 LoRA adapter → {OUTPUT_DIR}")
model.save_pretrained(OUTPUT_DIR)
processor.save_pretrained(OUTPUT_DIR)
print("LoRA adapter saved.")

# ── 6. Export merged model ─────────────────────────────────────────────────────
print(f"\nExporting merged 16-bit model → {MERGED_DIR}")
try:
    os.makedirs(MERGED_DIR, exist_ok=True)
    model.save_pretrained_merged(MERGED_DIR, processor, save_method="merged_16bit")
    print("Merged model saved.")
except Exception as e:
    print(f"Merged export skipped (non-fatal): {e}")

# ── 7. Export GGUF (optional — fails gracefully on broken llama.cpp installs) ──
print(f"\nExporting GGUF ({GGUF_QUANT}) → {GGUF_DIR}")
try:
    os.makedirs(GGUF_DIR, exist_ok=True)
    model.save_pretrained_gguf(GGUF_DIR, processor, quantization_method=GGUF_QUANT)
    from pathlib import Path
    for f in Path(GGUF_DIR).glob("*.gguf"):
        size_mb = f.stat().st_size / 1e6
        print(f"  {f.name}  ({size_mb:.0f} MB)")
except Exception as e:
    print(f"GGUF export skipped (non-fatal — llama.cpp conversion issue): {e}")
    print("LoRA adapter and merged model are sufficient for serving.")

print("\n" + "="*60)
print("DONE. Next steps:")
print(f"  1. Evaluate: python3 eval/evaluate_model_v2.py")
print(f"  2. Serve:    python3 serve/serve_v2.py  (port 9003)")
print(f"  3. Compare:  use /evaluate-finetune in Deep2Lead app")
print("="*60)
