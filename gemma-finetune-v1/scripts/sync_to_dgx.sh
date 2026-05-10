#!/bin/bash
# Sync gemma-finetune-v1/ code to DGX at ~/unsloth/gemma-4-finetune/
# Run ON MAC: bash gemma-finetune-v1/scripts/sync_to_dgx.sh

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOCAL_DIR="$REPO_ROOT/gemma-finetune-v1/"
REMOTE="dlyog@dgx1:/home/dlyog/unsloth/gemma-4-finetune/"

echo "Syncing $LOCAL_DIR → $REMOTE"
rsync -avz --progress \
    --exclude="__pycache__/" \
    --exclude="*.pyc" \
    --exclude=".DS_Store" \
    --exclude="drug_discovery/" \
    --exclude="data/*.jsonl" \
    "$LOCAL_DIR" "$REMOTE"

echo ""
echo "Sync complete. On DGX:"
echo "  cd ~/unsloth/gemma-4-finetune"
echo ""
echo "--- Quick start ---"
echo "  source ~/unsloth/.unsloth/bin/activate"
echo ""
echo "  # 1. Stop servers to free VRAM"
echo "  bash scripts/stop_servers.sh"
echo ""
echo "  # 2. Build dataset (first time ~10-20 min to download)"
echo "  python3 data/download_datasets.py"
echo "  python3 data/build_custom_dataset.py"
echo ""
echo "  # 3. Train (2-3 hours on GB10)"
echo "  nohup python3 train/finetune_gemma4.py 2>&1 | tee train.log &"
echo "  tail -f train.log"
echo ""
echo "  # 4. Evaluate"
echo "  python3 eval/evaluate_model.py"
echo ""
echo "  # 5. Serve (port 9002)"
echo "  screen -dmS gemma4_drug bash -c 'source ~/unsloth/.unsloth/bin/activate && python3 serve/serve_finetuned.py 2>&1 | tee serve/drug_api.log'"
