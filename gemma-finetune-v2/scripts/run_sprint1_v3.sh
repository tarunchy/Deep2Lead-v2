#!/usr/bin/env bash
# ============================================================
# Deep2Lead Sprint 1 — v3 Dataset Build + Overnight Training
#
# Runs on dgx1. Logs to ~/unsloth/gemma-4-finetune-v2/train_v3.log
#
# Steps:
#   [1] Clone Mol-Instructions (25K records)
#   [2] Parse BindingDB All TSV → bindingdb_parsed.jsonl
#   [3] Load Mol-Instructions → mol_instructions.jsonl
#   [4] Build merged v3 dataset (~220K records)
#   [5] Checkpoint: verify dataset > 40K records
#   [6] Launch v3 fine-tune (overnight, full 16-bit, r=64)
# ============================================================

set -e

PROJECT_DIR="$HOME/unsloth/gemma-4-finetune-v2"
VENV="$HOME/unsloth/.unsloth/bin/activate"
DATA_DIR="$HOME/data"
BINDINGDB_TSV="$DATA_DIR/BindingDB_All.tsv"
MOL_INST_DIR="$DATA_DIR/mol-instructions"

cd "$PROJECT_DIR"
source "$VENV"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "========================================="
log "Deep2Lead Sprint 1 — v3 Pipeline"
log "========================================="

# ── [1] Clone Mol-Instructions ────────────────────────────────────────────────
log "[1/6] Checking Mol-Instructions clone ..."
if [ ! -d "$MOL_INST_DIR" ]; then
    log "  Cloning from HuggingFace (git-lfs) ..."
    GIT_LFS_SKIP_SMUDGE=0 git clone https://huggingface.co/datasets/zjunlp/Mol-Instructions "$MOL_INST_DIR"
    log "  Clone complete."
else
    log "  Already cloned at $MOL_INST_DIR"
fi

# ── [2] Parse BindingDB All TSV ──────────────────────────────────────────────
log "[2/6] Parsing BindingDB All TSV (4.8GB — may take 15-20 min) ..."
if [ ! -f "$PROJECT_DIR/data/bindingdb_parsed.jsonl" ]; then
    python3 data/parse_bindingdb.py \
        --input "$BINDINGDB_TSV" \
        --output "$PROJECT_DIR/data/bindingdb_parsed.jsonl" \
        --cutoff 100 \
        --min-seq 50
    COUNT=$(wc -l < "$PROJECT_DIR/data/bindingdb_parsed.jsonl")
    log "  Parsed $COUNT BindingDB pairs."
else
    COUNT=$(wc -l < "$PROJECT_DIR/data/bindingdb_parsed.jsonl")
    log "  Already parsed: $COUNT records."
fi

# ── [3] Load Mol-Instructions ────────────────────────────────────────────────
log "[3/6] Loading Mol-Instructions → mol_instructions.jsonl ..."
if [ ! -f "$PROJECT_DIR/data/mol_instructions.jsonl" ]; then
    python3 data/load_mol_instructions.py \
        --local-dir "$MOL_INST_DIR" \
        --output "$PROJECT_DIR/data/mol_instructions.jsonl" \
        --max 25000
else
    COUNT=$(wc -l < "$PROJECT_DIR/data/mol_instructions.jsonl")
    log "  Already loaded: $COUNT records."
fi

# ── [4] Build merged v3 dataset ──────────────────────────────────────────────
log "[4/6] Building merged v3 dataset ..."
BINDINGDB_JSONL="$PROJECT_DIR/data/bindingdb_parsed.jsonl" \
    python3 data/build_dataset_v3.py

# ── [5] Checkpoint ───────────────────────────────────────────────────────────
log "[5/6] Checkpoint: verifying dataset size ..."
V3_PATH="$PROJECT_DIR/data/merged_finetune_v3.jsonl"
if [ ! -f "$V3_PATH" ]; then
    log "  ERROR: $V3_PATH not found!"
    exit 1
fi
TOTAL=$(wc -l < "$V3_PATH")
log "  Total records: $TOTAL"
if [ "$TOTAL" -lt 40000 ]; then
    log "  ERROR: Dataset too small ($TOTAL < 40K). Aborting training."
    exit 1
fi
log "  GO — dataset is large enough."

# ── [6] Launch v3 fine-tune ──────────────────────────────────────────────────
log "[6/6] Launching v3 fine-tune (this runs overnight) ..."
python3 train/finetune_gemma4_v3.py

log "========================================="
log "Sprint 1 COMPLETE"
log "========================================="
