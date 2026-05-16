"""
Central configuration for Gemma4-E2B drug-discovery fine-tuning v2.
Key upgrades over v1:
  - LoRA r=32, alpha=64 with RS-LoRA (rank-stabilized)
  - Dataset: 65% ChEMBL/BindingDB, 25% Mol-Instructions, 10% MOSES
  - IBM MAMMAL (ibm/biomed.omics.bl.sm.ma-ted-458m) as affinity filter
  - Rationale-first ChatML format for chain-of-thought protein→scaffold mapping
  - Port 9003 (alongside v1 at 9002)
"""

import os

# ── Model ──────────────────────────────────────────────────────────────────────
MODEL_NAME       = "unsloth/gemma-4-E2B-it-unsloth-bnb-4bit"
MAX_SEQ_LENGTH   = 4096
LOAD_IN_4BIT     = True

# ── LoRA v2 ────────────────────────────────────────────────────────────────────
LORA_R           = 32           # doubled from v1 (16 → 32)
LORA_ALPHA       = 64           # doubled from v1 (32 → 64)
LORA_DROPOUT     = 0
USE_RSLORA       = True         # rank-stabilized LoRA for stable high-rank training
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

# ── Training ───────────────────────────────────────────────────────────────────
BATCH_SIZE       = 4
GRAD_ACCUM       = 8            # effective batch = 32
NUM_EPOCHS       = 3
LEARNING_RATE    = 1.5e-4       # slightly lower than v1 (2e-4) for high-rank stability
LR_SCHEDULER     = "cosine"
WARMUP_RATIO     = 0.05
WEIGHT_DECAY     = 0.01
SEED             = 42

# ── Dataset v2 targets (samples) ───────────────────────────────────────────────
CHEMBL_TARGET_SAMPLES    = 65_000   # 65% — protein FASTA + SMILES pairs (IC50 < 100 nM)
MOL_INSTRUCTIONS_SAMPLES = 25_000   # 25% — reasoning, captioning, reaction
MOSES_SAMPLES            = 10_000   # 10% — SMILES syntax baseline (downsampled from v1)

# Affinity threshold for IBM MAMMAL gatekeeper (0.0–1.0)
# Empirically calibrated: model's pKd predictions cluster 5.2–5.6 for most pairs
# (the official IBM default pair scores 0.549). Threshold of 0.55 accepts genuine
# nanomolar binders while filtering the lowest-confidence predictions.
# Training mean pKd = 5.79 → score ≈ 0.579; threshold is one std below that.
MAMMAL_AFFINITY_THRESHOLD = 0.55

# ChEMBL activity cutoffs (nM) — keep only high-affinity binders
CHEMBL_IC50_CUTOFF_NM    = 100
CHEMBL_KI_CUTOFF_NM      = 100

# ── Dataset paths ───────────────────────────────────────────────────────────────
CHEMBL_PAIRS_PATH        = "./data/chembl_bindingdb_pairs.jsonl"
CUSTOM_DATASET_PATH      = "./data/deep2lead_custom_v2.jsonl"
MERGED_DATASET_PATH      = "./data/merged_finetune_v2.jsonl"

# ── Output ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR       = "./drug_discovery/lora/gemma4_e2b_drug_v2"
MERGED_DIR       = "./drug_discovery/lora/gemma4_e2b_drug_v2_merged"
GGUF_DIR         = "./drug_discovery/gguf/gemma4_e2b_drug_v2"
GGUF_QUANT       = "q4_k_m"

# ── DGX / serve ────────────────────────────────────────────────────────────────
DGX_HOST           = "dlyog@dgx1"
DGX_FINETUNE_DIR   = "/home/dlyog/unsloth/gemma-4-finetune-v2"   # separate from v1
FINETUNED_API_PORT = 9003                                          # v1 is 9002, v2 is 9003

# ── Target targets JSON (shared with v1 app) ────────────────────────────────────
_local_targets = os.path.join(os.path.dirname(__file__), "..", "v2", "data", "curated_targets.json")
_dgx_targets   = os.path.join(os.path.dirname(__file__), "data", "curated_targets.json")
TARGETS_JSON_PATH = _local_targets if os.path.exists(_local_targets) else _dgx_targets
