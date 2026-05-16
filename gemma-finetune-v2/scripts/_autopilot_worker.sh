#!/usr/bin/env bash
# Internal worker — called by autopilot_v3.sh inside tmux. Do not call directly.

PROJECT="$HOME/unsloth/gemma-4-finetune-v2"
VENV="$HOME/unsloth/.unsloth/bin/activate"
LOG="$PROJECT/TRAIN_V3.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# Route all output to log
exec >> "$LOG" 2>&1

log "======================================================"
log " Deep2Lead v3 Autopilot Starting"
log "======================================================"

source "$VENV"
cd "$PROJECT"

# ── Sanity checks ─────────────────────────────────────────
log "[CHECK] Dataset ..."
if [ ! -f "./data/merged_finetune_v3.jsonl" ]; then
    log "ERROR: Dataset missing. Rebuilding ..."
    BINDINGDB_JSONL="$HOME/data/bindingdb_parsed.jsonl" python3 data/build_dataset_v3.py
fi
NREC=$(wc -l < ./data/merged_finetune_v3.jsonl)
log "[CHECK] Dataset: $NREC records"
if [ "$NREC" -lt 40000 ]; then
    log "ERROR: Dataset too small ($NREC). Aborting."
    exit 1
fi

log "[CHECK] GPU ..."
python3 -c "import torch; assert torch.cuda.is_available(), 'No GPU!'; \
    print(f'  GPU: {torch.cuda.get_device_name(0)}  VRAM: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB')"

log "[CHECK] Unsloth ..."
python3 -c "from unsloth import FastModel; print('  unsloth OK')"

# ── Training ──────────────────────────────────────────────
log "[TRAIN] Starting finetune_gemma4_v3.py ..."
log "[TRAIN] This will run for several hours. Monitor with:"
log "[TRAIN]   ssh dgx1 'tail -f $LOG'"

python3 train/finetune_gemma4_v3.py
EXIT=$?

# ── Result ────────────────────────────────────────────────
if [ $EXIT -eq 0 ]; then
    log "======================================================"
    log " V3 TRAINING COMPLETE — EXIT 0"
    log " Adapter : ./drug_discovery/lora/gemma4_e2b_drug_v3"
    log " Merged  : ./drug_discovery/lora/gemma4_e2b_drug_v3_merged"
    log " Next    : run eval/run_full_eval.py"
    log "======================================================"
else
    log "======================================================"
    log " ERROR: Training exited with code $EXIT"
    log " Check log above for traceback."
    log "======================================================"
fi
