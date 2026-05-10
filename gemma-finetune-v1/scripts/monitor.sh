#!/bin/bash
# Monitor the fine-tuning pipeline progress from Mac.
# Usage: bash gemma-finetune-v1/scripts/monitor.sh
# Press Ctrl+C to exit.

DGX="dlyog@dgx1"
REMOTE_LOG="/home/dlyog/unsloth/gemma-4-finetune/pipeline.log"
REFRESH=30   # seconds between GPU stats refresh

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Gemma4-E2B Fine-Tuning Monitor"
echo "  DGX: $DGX"
echo "  Log: $REMOTE_LOG"
echo "  GPU stats refresh: every ${REFRESH}s"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check pipeline is actually running
PID=$(ssh "$DGX" "pgrep -f run_pipeline.sh" 2>/dev/null || true)
if [ -z "$PID" ]; then
    # Check if training is running directly
    PID=$(ssh "$DGX" "pgrep -f finetune_gemma4" 2>/dev/null || true)
fi

if [ -z "$PID" ]; then
    echo "⚠  No pipeline process detected on DGX."
    echo "   Check if it's still in the dataset download phase (python3 data/*)."
    echo ""
fi

# Determine current step from last log lines
current_step() {
    ssh "$DGX" "tail -20 $REMOTE_LOG 2>/dev/null" | grep "STEP\|loss\|Training complete\|Epoch\|steps" | tail -5
}

# Show GPU stats
gpu_stats() {
    echo ""
    echo "── GPU $(date '+%H:%M:%S') ────────────────────────────────────"
    ssh "$DGX" "nvidia-smi --query-gpu=name,memory.free,memory.used,utilization.gpu \
        --format=csv,noheader 2>/dev/null | awk -F',' \
        '{printf \"  %-20s | Free: %s | Used: %s | Util: %s\n\", \$1, \$2, \$3, \$4}'" 2>/dev/null || echo "  (GPU stats unavailable)"
    echo ""
}

# Show last few log lines with step detection
show_progress() {
    echo "── Progress ────────────────────────────────────────────"
    ssh "$DGX" "tail -30 $REMOTE_LOG 2>/dev/null" || echo "  Log not yet created."
    echo ""
}

# Initial state
gpu_stats
show_progress

# Tail the log live, refresh GPU every REFRESH seconds
echo "── Live log tail (Ctrl+C to stop) ─────────────────────"
COUNTER=0
ssh "$DGX" "tail -f $REMOTE_LOG 2>/dev/null" | while IFS= read -r line; do
    echo "$line"
    COUNTER=$((COUNTER + 1))
    # Every N lines, print a GPU snapshot inline
    if [ $((COUNTER % 50)) -eq 0 ]; then
        echo ""
        echo "  ── GPU snapshot ──────────────────────────────────────"
        ssh "$DGX" "nvidia-smi --query-gpu=memory.free,memory.used,utilization.gpu \
            --format=csv,noheader 2>/dev/null" 2>/dev/null | awk -F',' \
            '{printf "  Free: %s | Used: %s | GPU util: %s\n", $1, $2, $3}'
        echo ""
    fi
done
