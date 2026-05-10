#!/bin/bash
# Restart model servers after fine-tuning is complete.
# Run ON DGX: bash scripts/start_servers.sh

set -e

echo "=== Restarting model servers ==="

# 1. Restart Docker model containers
echo "[1/2] Starting Docker containers..."
for container in qwen35-api text2image-api; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        docker start "$container"
        echo "     Started: $container"
    else
        echo "     Container not found: $container (skipping)"
    fi
done

# 2. Restart Gemma4-E4B API server in screen
echo "[2/2] Starting Gemma4-E4B API server (screen: gemma4_api, port 9001)..."
if screen -list | grep -q "gemma4_api"; then
    echo "     Screen session already exists — skipping."
else
    screen -dmS gemma4_api bash -c "
        source ~/unsloth/.unsloth/bin/activate
        echo 'Starting Gemma4-E4B API...'
        python3 /home/dlyog/unsloth/gemma4/gemma4_api_server.py --port 9001 2>&1 | tee /home/dlyog/unsloth/gemma4/gemma4_api.log
    "
    echo "     Screen session 'gemma4_api' started."
    echo "     Watch logs: screen -r gemma4_api"
fi

echo ""
echo "=== GPU memory after restart ==="
sleep 3
nvidia-smi --query-gpu=memory.free,memory.total,memory.used --format=csv,noheader,nounits | \
    awk '{printf "Free: %s MB | Used: %s MB | Total: %s MB\n", $1, $3, $2}'

echo ""
echo "Services:"
echo "  E4B base model:  http://dgx1:9001/health"
echo "  E2B fine-tuned:  http://dgx1:9002/health  (if running)"
echo ""
echo "To start the fine-tuned E2B server:"
echo "  cd ~/unsloth/gemma-4-finetune"
echo "  screen -dmS gemma4_drug bash -c 'source ~/unsloth/.unsloth/bin/activate && python3 serve/serve_finetuned.py --port 9002 2>&1 | tee serve/drug_api.log'"
