#!/usr/bin/env bash
# ============================================================
# Deep2Lead v3 — AUTOPILOT TRAINING LAUNCHER
#
# Fully autonomous. Run once, walk away.
# All output → ~/unsloth/gemma-4-finetune-v2/TRAIN_V3.log
#
# Usage (run on dgx1):
#   bash scripts/autopilot_v3.sh
#
# Monitor from anywhere:
#   ssh dgx1 'tail -f ~/unsloth/gemma-4-finetune-v2/TRAIN_V3.log'
#
# Check status:
#   ssh dgx1 'grep -E "Step|loss|V3 TRAINING COMPLETE|ERROR|EXIT" ~/unsloth/gemma-4-finetune-v2/TRAIN_V3.log | tail -5'
# ============================================================

PROJECT="$HOME/unsloth/gemma-4-finetune-v2"
VENV="$HOME/unsloth/.unsloth/bin/activate"
LOG="$PROJECT/TRAIN_V3.log"
SESSION="autopilot_v3"

# Kill any existing session with this name
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Launch in detached tmux — survives SSH disconnect
tmux new-session -d -s "$SESSION" -x 250 -y 50 "bash $PROJECT/scripts/_autopilot_worker.sh"

echo ""
echo "========================================="
echo " V3 Training launched in background"
echo " Session : $SESSION"
echo " Log     : $LOG"
echo "========================================="
echo ""
echo " MONITOR COMMAND:"
echo "   ssh dgx1 'tail -f ~/unsloth/gemma-4-finetune-v2/TRAIN_V3.log'"
echo ""
echo " QUICK STATUS:"
echo "   ssh dgx1 'grep -E \"Step|loss|COMPLETE|ERROR\" ~/unsloth/gemma-4-finetune-v2/TRAIN_V3.log | tail -5'"
echo ""
echo " GPU CHECK:"
echo "   ssh dgx1 nvidia-smi"
echo ""
echo " You can now close this terminal and go to sleep."
echo "========================================="
