#!/usr/bin/env bash
# auto_eval_stop.sh — watch training, eval each new checkpoint, stop when quality gate passes
#
# Usage:
#   bash eval/auto_eval_stop.sh [training_pid]
#   If PID omitted, auto-detects via pgrep.
#
# Quality gate: >=2/3 valid SMILES AND avg QED >= 0.55
# Checks every 60s; only runs eval when a NEW checkpoint folder appears (every ~500 steps).

set -euo pipefail

TRAINING_PID=${1:-$(pgrep -f finetune_gemma4 | head -1)}
LOG=~/unsloth/gemma-4-finetune-v2/TRAIN_V3.log
CKPT_DIR=~/unsloth/gemma-4-finetune-v2/drug_discovery/lora/gemma4_e2b_drug_v3
EVAL_SCRIPT=~/unsloth/gemma-4-finetune-v2/eval/quick_check.py
VENV=~/.unsloth/.unsloth/bin/activate

VALID_THRESHOLD=2    # out of 3
QED_THRESHOLD=0.55

# ── helpers ──────────────────────────────────────────────────────────────────
log() { echo "[$(date '+%H:%M:%S')] $*"; }

current_step() {
    grep -oE '[0-9]+/3518' "$LOG" 2>/dev/null | tail -1 | cut -d/ -f1 || echo "?"
}

latest_checkpoint() {
    ls -d "$CKPT_DIR"/checkpoint-* 2>/dev/null \
        | sort -t- -k2 -n | tail -1
}

run_eval() {
    local ckpt=$1
    source "$VENV"
    python3 "$EVAL_SCRIPT" --checkpoint "$ckpt" 2>&1
}

parse_valid() { grep "SMILES validity" <<< "$1" | grep -oE '[0-9]+/[0-9]+' | cut -d/ -f1; }
parse_qed()   { grep "Average QED"    <<< "$1" | grep -oE '[0-9]+\.[0-9]+'; }

# ── main loop ────────────────────────────────────────────────────────────────
log "Monitoring training PID $TRAINING_PID"
log "Gate: >=${VALID_THRESHOLD}/3 valid SMILES  AND  QED >= ${QED_THRESHOLD}"
log "Polling every 60s; eval fires on each new checkpoint..."
echo ""

LAST_CKPT=""

while kill -0 "$TRAINING_PID" 2>/dev/null; do
    STEP=$(current_step)
    LATEST=$(latest_checkpoint)

    if [[ -n "$LATEST" && "$LATEST" != "$LAST_CKPT" ]]; then
        CKPT_STEP=$(basename "$LATEST" | grep -oE '[0-9]+')
        log "━━━ New checkpoint: step $CKPT_STEP ($LATEST) ━━━"

        RESULT=$(run_eval "$LATEST")
        echo "$RESULT"

        VALID=$(parse_valid "$RESULT")
        QED=$(parse_qed "$RESULT")

        log "Valid: ${VALID}/3 | QED: ${QED} | Training step: ${STEP}/3518"

        if [[ -n "$VALID" && -n "$QED" ]] \
           && [[ "$VALID" -ge "$VALID_THRESHOLD" ]] \
           && (( $(echo "$QED >= $QED_THRESHOLD" | bc -l) )); then
            echo ""
            log "✓ QUALITY GATE PASSED — stopping training at step $CKPT_STEP"
            kill -SIGTERM "$TRAINING_PID"
            log "SIGTERM sent to PID $TRAINING_PID — trainer will save final checkpoint"
            echo ""
            echo "Best checkpoint: $LATEST"
            echo "Run full eval:   python3 eval/run_full_eval.py --checkpoint $LATEST"
            exit 0
        else
            log "Gate not met yet — continuing..."
        fi

        LAST_CKPT="$LATEST"
    fi

    sleep 60
done

log "Training process ended (PID $TRAINING_PID gone)"
LATEST=$(latest_checkpoint)
echo "Last checkpoint: $LATEST"
