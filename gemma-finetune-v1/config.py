"""
Central configuration for Gemma4-E2B drug-discovery fine-tuning.
All tunable knobs live here — nothing is hardcoded in the other modules.
"""

import os

# ── Model ──────────────────────────────────────────────────────────────────────
MODEL_NAME       = "unsloth/gemma-4-E2B-it-unsloth-bnb-4bit"
MAX_SEQ_LENGTH   = 4096
LOAD_IN_4BIT     = True

# ── LoRA ───────────────────────────────────────────────────────────────────────
LORA_R           = 16
LORA_ALPHA       = 32
LORA_DROPOUT     = 0
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

# ── Training ───────────────────────────────────────────────────────────────────
BATCH_SIZE       = 4         # per device; increase after stopping servers
GRAD_ACCUM       = 8         # effective batch = 32
NUM_EPOCHS       = 3
LEARNING_RATE    = 2e-4
LR_SCHEDULER     = "cosine"
WARMUP_RATIO     = 0.05
WEIGHT_DECAY     = 0.01
SEED             = 42

# ── Dataset ────────────────────────────────────────────────────────────────────
SMOLINSTRUCT_TASKS = [
    "molecule_generation",
    "text_to_mol",
    "property_prediction",
    "mol_to_text",
    "forward_reaction_prediction",
    "retrosynthesis",
]
SMOLINSTRUCT_MAX_SAMPLES = 80_000   # subset for practical training time
CUSTOM_DATASET_PATH      = "./data/deep2lead_custom.jsonl"
MERGED_DATASET_PATH      = "./data/merged_finetune.jsonl"

# ── Output ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR       = "./drug_discovery/lora/gemma4_e2b_drug_v1"
MERGED_DIR       = "./drug_discovery/lora/gemma4_e2b_drug_merged"
GGUF_DIR         = "./drug_discovery/gguf/gemma4_e2b_drug_v1"
GGUF_QUANT       = "q4_k_m"

# ── DGX / serve ────────────────────────────────────────────────────────────────
DGX_HOST         = "dlyog@dgx1"
DGX_FINETUNE_DIR = "/home/dlyog/unsloth/gemma-4-finetune"
FINETUNED_API_PORT = 9002          # A/B alongside existing E4B at 9001

# ── Paths on DGX (relative to DGX_FINETUNE_DIR) ────────────────────────────────
TARGETS_JSON_PATH = os.path.join(
    os.path.dirname(__file__), "..", "v2", "data", "curated_targets.json"
)
