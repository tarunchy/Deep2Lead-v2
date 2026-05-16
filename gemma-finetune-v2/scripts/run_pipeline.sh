#!/usr/bin/env bash
# Run the complete v2 fine-tuning pipeline on DGX1.
# Assumes: ~/unsloth/.unsloth/bin/activate exists, cwd = /home/dlyog/unsloth/gemma-4-finetune-v2

set -e

VENV="$HOME/unsloth/.unsloth/bin/activate"
if [[ ! -f "$VENV" ]]; then
    echo "ERROR: unsloth venv not found at $VENV"
    exit 1
fi

source "$VENV"
cd "$(dirname "$0")/.."

echo "======================================================"
echo " Deep2Lead Gemma4-E2B v2 Fine-Tuning Pipeline"
echo "======================================================"
echo ""

echo "[Step 1/4] Build Deep2Lead custom v2 dataset"
python3 data/build_custom_dataset_v2.py
echo ""

echo "[Step 2/4] Download + filter main datasets (ChEMBL/BindingDB/MAMMAL)"
python3 data/download_datasets_v2.py
echo ""

echo "[Step 3/4] Fine-tune Gemma4-E2B with v2 LoRA config"
python3 train/finetune_gemma4_v2.py
echo ""

echo "[Step 4/4] Evaluate v2 model"
python3 eval/evaluate_model_v2.py
echo ""

echo "======================================================"
echo " Pipeline complete!"
echo " Serve:   python3 serve/serve_v2.py  (port 9003)"
echo "======================================================"
