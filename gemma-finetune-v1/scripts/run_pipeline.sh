#!/bin/bash
# Full fine-tuning pipeline — runs sequentially, everything logged.
# Launched in background via: nohup bash scripts/run_pipeline.sh > pipeline.log 2>&1 &
# Monitor with: bash scripts/monitor.sh  (from Mac)

set -e

LOG="$(cd "$(dirname "$0")/.." && pwd)/pipeline.log"
VENV="$HOME/unsloth/.unsloth/bin/activate"
BASE="$(cd "$(dirname "$0")/.." && pwd)"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

separator() {
    echo "" | tee -a "$LOG"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG"
    log "$1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG"
    echo "" | tee -a "$LOG"
}

cd "$BASE"
echo "================================================================" | tee "$LOG"
log "GEMMA4-E2B DRUG DISCOVERY FINE-TUNING PIPELINE STARTED"
log "Working dir: $BASE"
log "Log file:    $LOG"
echo "================================================================" | tee -a "$LOG"

# ── STEP 1: Stop servers ───────────────────────────────────────────────────────
separator "STEP 1/5 — Stopping model servers to free VRAM"

log "Stopping Gemma4-E4B screen session (port 9001)..."
if screen -list 2>/dev/null | grep -q "gemma4_api"; then
    screen -S gemma4_api -X quit
    log "  screen 'gemma4_api' terminated."
else
    log "  screen 'gemma4_api' not running."
fi

if lsof -ti:9001 > /dev/null 2>&1; then
    kill -9 $(lsof -ti:9001) 2>/dev/null || true
    log "  Killed lingering process on port 9001."
fi

log "Stopping Docker model containers..."
for container in qwen35-api text2image-api; do
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"; then
        docker stop "$container" >> "$LOG" 2>&1
        log "  Stopped container: $container"
    else
        log "  Container '$container' not running — skipping."
    fi
done

# Also kill port 8005 (old uvicorn api_server — 4.7 GB GPU)
log "Stopping port 8005 (old api_server uvicorn)..."
if lsof -ti:8005 > /dev/null 2>&1; then
    kill -9 $(lsof -ti:8005) 2>/dev/null || true
    log "  Killed process on port 8005."
else
    log "  Nothing on port 8005."
fi

sleep 5   # let processes fully release GPU memory

# ── STEP 2: Validate VRAM is free ─────────────────────────────────────────────
separator "STEP 2/5 — Validating GPU memory is free"

log "GPU state after stopping servers:"
nvidia-smi --query-gpu=name,memory.free,memory.used,memory.total \
    --format=csv,noheader 2>/dev/null | while IFS=',' read name free used total; do
    log "  GPU: $name"
    log "  Free:  $free"
    log "  Used:  $used"
    log "  Total: $total"
done

log ""
log "Running processes still using GPU:"
nvidia-smi | grep -E "python|MiB" | tee -a "$LOG" || log "  (none found)"

# ── STEP 3: Activate venv + install extras if needed ──────────────────────────
separator "STEP 3/5 — Activating unsloth venv + verifying dependencies"

source "$VENV"
log "Python: $(python3 --version)"
log "PyTorch: $(python3 -c 'import torch; print(torch.__version__)')"
log "CUDA available: $(python3 -c 'import torch; print(torch.cuda.is_available())')"

log "Checking rdkit..."
python3 -c "from rdkit import Chem; print('  rdkit OK')" 2>/dev/null | tee -a "$LOG" || {
    log "  rdkit not found — installing..."
    pip install rdkit -q | tee -a "$LOG"
}

# ── STEP 4: Build datasets ─────────────────────────────────────────────────────
separator "STEP 4/5 — Building training datasets"

# 4a. Custom Deep2Lead dataset (fast — uses local targets JSON)
log "[4a] Building Deep2Lead custom dataset (~1 min)..."
python3 data/build_custom_dataset.py 2>&1 | tee -a "$LOG"
log "Custom dataset done."

# 4b. SMolInstruct + MOSES download (slow — ~10-20 min)
log "[4b] Downloading SMolInstruct + MOSES from HuggingFace (~10-20 min)..."
log "     This is the slow step — dataset is ~3M samples, filtering to 80K."
python3 data/download_datasets.py 2>&1 | tee -a "$LOG"
log "Dataset download complete."

# ── STEP 5: Train ──────────────────────────────────────────────────────────────
separator "STEP 5/5 — Fine-tuning Gemma4-E2B (QLoRA)"

log "GPU memory before training:"
nvidia-smi --query-gpu=memory.free,memory.used --format=csv,noheader 2>/dev/null | tee -a "$LOG"

log "Starting training..."
log "Estimated time: 2-3 hours on GB10"
log ""

python3 train/finetune_gemma4.py 2>&1 | tee -a "$LOG"

# ── DONE ───────────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "================================================================" | tee -a "$LOG"
log "PIPELINE COMPLETE!"
log "Outputs:"
log "  LoRA adapter:    $BASE/drug_discovery/lora/gemma4_e2b_drug_v1/"
log "  Merged model:    $BASE/drug_discovery/lora/gemma4_e2b_drug_merged/"
log "  GGUF (Mac):      $BASE/drug_discovery/gguf/gemma4_e2b_drug_v1/"
log ""
log "Next steps:"
log "  1. Evaluate:   python3 eval/evaluate_model.py"
log "  2. Serve:      python3 serve/serve_finetuned.py --port 9002"
log "  3. Restart old servers: bash scripts/start_servers.sh"
echo "================================================================" | tee -a "$LOG"
