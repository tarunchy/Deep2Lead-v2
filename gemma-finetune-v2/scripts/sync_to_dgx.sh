#!/usr/bin/env bash
# Sync local gemma-finetune-v2/ to dgx1 WITHOUT touching v1 directory.
# v1 dir: /home/dlyog/unsloth/gemma-4-finetune      ← never touched
# v2 dir: /home/dlyog/unsloth/gemma-4-finetune-v2   ← this script's target

set -e

DGX_HOST="dlyog@dgx1"
DGX_DIR="/home/dlyog/unsloth/gemma-4-finetune-v2"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Syncing v2 code to dgx1 ..."
echo "  Local:  $LOCAL_DIR"
echo "  Remote: $DGX_HOST:$DGX_DIR"
echo ""

# Create remote directory structure
ssh "$DGX_HOST" "mkdir -p $DGX_DIR/{data,train,eval,serve,scripts,drug_discovery}"

# Rsync code — exclude large generated data and checkpoints
rsync -avz --progress \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    --exclude="drug_discovery/" \
    --exclude="data/*.jsonl" \
    --exclude="data/*.json" \
    --exclude=".DS_Store" \
    "$LOCAL_DIR/" \
    "$DGX_HOST:$DGX_DIR/"

echo ""
echo "Sync complete."
echo ""
echo "To start v2 training:"
echo "  ssh $DGX_HOST"
echo "  cd $DGX_DIR"
echo "  screen -S gemma4_drug_v2"
echo "  bash scripts/run_pipeline.sh"
echo ""
echo "To start v2 serve API (port 9003):"
echo "  ssh $DGX_HOST"
echo "  cd $DGX_DIR"
echo "  screen -S gemma4_serve_v2"
echo "  source ~/unsloth/.unsloth/bin/activate"
echo "  python3 serve/serve_v2.py"
