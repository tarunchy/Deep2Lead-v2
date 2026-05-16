#!/usr/bin/env bash
# ============================================================
# Deep2Lead Gemma4-E2B v2 — Full Training Pipeline
# No shortcuts. Every step runs completely before the next.
#
# Prerequisites (must be done manually first):
#   1. On dlyog03: cd /home/dlyog/apps/ibm_biomed && bash setup.sh
#   2. On dlyog03: bash start.sh
#   3. Verify API: curl http://192.168.86.20:8090/health
#   4. Then run this script on dgx1
#
# Steps:
#   [1] Verify MAMMAL API is up on dlyog03
#   [2] Build Deep2Lead custom v2 dataset (rationale-first ChatML)
#   [3] Download ChEMBL high-affinity pairs (EBI REST API, may take hours)
#   [4] Filter ChEMBL pairs through IBM MAMMAL (dlyog03:8090)
#   [5] Download Mol-Instructions (25%) from HuggingFace
#   [6] Download MOSES contextualized (10%) from HuggingFace
#   [7] Merge all datasets
#   [8] Fine-tune Gemma4-E2B v2 (r=32, RS-LoRA, rationale-first)
#   [9] Evaluate v2 model
#   [10] Start v2 serve API on port 9003
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$HOME/unsloth/.unsloth/bin/activate"
MAMMAL_HOST="192.168.86.20"
MAMMAL_PORT="8090"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

source "$VENV"
cd "$PROJECT_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

echo ""
echo "============================================================"
echo " Deep2Lead Gemma4-E2B v2 — Full Training Pipeline"
echo " Started: $(ts)"
echo " Project: $PROJECT_DIR"
echo "============================================================"
echo ""

# ── Step 1: Verify MAMMAL API ─────────────────────────────────────────────────
echo "[Step 1/10] Verifying IBM MAMMAL API on dlyog03:${MAMMAL_PORT} ..."
MAMMAL_STATUS=$(curl -sf "http://${MAMMAL_HOST}:${MAMMAL_PORT}/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "unreachable")

if [[ "$MAMMAL_STATUS" == "ready" ]]; then
    echo "  MAMMAL API: READY"
    GPU=$(curl -sf "http://${MAMMAL_HOST}:${MAMMAL_PORT}/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('gpu','?'))" 2>/dev/null)
    echo "  GPU: $GPU"
    export MAMMAL_API_HOST="$MAMMAL_HOST"
    export MAMMAL_API_PORT="$MAMMAL_PORT"
else
    echo ""
    echo "  ERROR: MAMMAL API is not ready (status=$MAMMAL_STATUS)"
    echo "  On dlyog03, run:"
    echo "    cd /home/dlyog/apps/ibm_biomed"
    echo "    bash setup.sh        # if not done yet (~30 min)"
    echo "    bash start.sh        # then start the API"
    echo "    curl http://localhost:${MAMMAL_PORT}/health"
    echo ""
    echo "  Re-run this pipeline after MAMMAL API is ready."
    exit 1
fi
echo ""

# ── Step 2: Build custom v2 dataset ──────────────────────────────────────────
echo "[Step 2/10] Building Deep2Lead custom v2 dataset (rationale-first ChatML) ..."
python3 data/build_custom_dataset_v2.py 2>&1 | tee "$LOG_DIR/step2_custom.log"
echo "  Done. Log: $LOG_DIR/step2_custom.log"
echo ""

# ── Step 3: Download ChEMBL pairs from EBI REST API ──────────────────────────
echo "[Step 3/10] Downloading ChEMBL high-affinity pairs from EBI API ..."
echo "  Target: 65,000 pairs with IC50 ≤ 100 nM"
echo "  This step pages through ChEMBL REST API — may take 2-6 hours."
echo "  Progress is saved incrementally — safe to interrupt and resume."
echo ""
python3 data/download_chembl.py \
    --max-pairs 65000 \
    --output ./data/chembl_bindingdb_pairs.jsonl \
    --ic50-cutoff 100.0 \
    2>&1 | tee "$LOG_DIR/step3_chembl.log"
echo "  Done. Log: $LOG_DIR/step3_chembl.log"
echo ""

# ── Step 4: Filter through IBM MAMMAL (happens inside download_datasets_v2.py)
# ── Step 5 & 6: Download Mol-Instructions + MOSES
# ── Step 7: Merge all datasets
echo "[Steps 4-7/10] MAMMAL filter + Mol-Instructions + MOSES + Merge ..."
echo "  MAMMAL filter will call dlyog03:${MAMMAL_PORT} during this step."
python3 data/download_datasets_v2.py 2>&1 | tee "$LOG_DIR/step4_7_datasets.log"
echo "  Done. Log: $LOG_DIR/step4_7_datasets.log"
echo ""

# Verify dataset size
TOTAL=$(wc -l < ./data/merged_finetune_v2.jsonl 2>/dev/null || echo 0)
echo "  Merged dataset: ${TOTAL} records"
if [[ "$TOTAL" -lt 100 ]]; then
    echo "  WARNING: Dataset is very small (${TOTAL} records)."
    echo "  Check logs above. Training will proceed but results may be limited."
fi
echo ""

# ── Step 8: Fine-tune Gemma4-E2B v2 ──────────────────────────────────────────
echo "[Step 8/10] Fine-tuning Gemma4-E2B v2 (r=32, RS-LoRA, 3 epochs) ..."
echo "  This step takes ~4-8 hours depending on dataset size."
python3 train/finetune_gemma4_v2.py 2>&1 | tee "$LOG_DIR/step8_train.log"
echo "  Done. Log: $LOG_DIR/step8_train.log"
echo ""

# ── Step 9: Evaluate ──────────────────────────────────────────────────────────
echo "[Step 9/10] Evaluating v2 model ..."
python3 eval/evaluate_model_v2.py \
    --lora-path ./drug_discovery/lora/gemma4_e2b_drug_v2 \
    --n-prompts 30 \
    2>&1 | tee "$LOG_DIR/step9_eval.log"
echo "  Done. Log: $LOG_DIR/step9_eval.log"
echo ""

# ── Step 10: Start serve API ──────────────────────────────────────────────────
echo "[Step 10/10] Starting v2 serve API on port 9003 ..."
screen -S gemma4_serve_v2 -X quit 2>/dev/null || true
sleep 2
screen -dmS gemma4_serve_v2 bash -c "
    source $VENV
    cd $PROJECT_DIR
    python3 serve/serve_v2.py 2>&1 | tee serve_v2.log
"
sleep 5
if screen -list | grep -q gemma4_serve_v2; then
    echo "  Serve API started in screen session 'gemma4_serve_v2'"
    echo "  Monitor: tail -f $PROJECT_DIR/serve_v2.log"
    echo "  Health:  curl http://localhost:9003/health"
else
    echo "  WARNING: Serve screen failed to start. Run manually:"
    echo "    screen -dmS gemma4_serve_v2 bash -c 'source $VENV && cd $PROJECT_DIR && python3 serve/serve_v2.py | tee serve_v2.log'"
fi

echo ""
echo "============================================================"
echo " PIPELINE COMPLETE"
echo " Finished: $(ts)"
echo ""
echo " Logs: $LOG_DIR/"
echo " Adapter: $PROJECT_DIR/drug_discovery/lora/gemma4_e2b_drug_v2/"
echo " Eval:    $PROJECT_DIR/drug_discovery/lora/gemma4_e2b_drug_v2/eval_results_v2.json"
echo ""
echo " In Deep2Lead app: select 'Fine-tuned v2 (dgx1:9003)' in model selector"
echo "============================================================"
