#!/bin/bash
# Stop the Gemma4-E4B server (port 9001) and Docker model containers
# to free VRAM for fine-tuning training.
# Run ON DGX: bash scripts/stop_servers.sh

set -e

echo "=== Stopping model servers to free VRAM ==="

# 1. Kill the gemma4_api screen session (E4B at port 9001)
echo "[1/2] Stopping Gemma4-E4B API server (screen: gemma4_api, port 9001)..."
if screen -list | grep -q "gemma4_api"; then
    screen -S gemma4_api -X quit
    echo "     Screen session 'gemma4_api' terminated."
else
    echo "     Screen session 'gemma4_api' not found (may already be stopped)."
fi

# Also kill any lingering python process on port 9001
if lsof -ti:9001 > /dev/null 2>&1; then
    echo "     Killing remaining process on port 9001..."
    kill -9 $(lsof -ti:9001) 2>/dev/null || true
fi

# 2. Stop Docker model containers
echo "[2/2] Stopping Docker model containers..."
for container in qwen35-api text2image-api; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        docker stop "$container"
        echo "     Stopped: $container"
    else
        echo "     Not running: $container"
    fi
done

# 3. Show remaining VRAM
echo ""
echo "=== Current GPU memory usage ==="
nvidia-smi --query-gpu=memory.free,memory.total,memory.used --format=csv,noheader,nounits | \
    awk '{printf "Free: %s MB | Used: %s MB | Total: %s MB\n", $1, $3, $2}'

echo ""
echo "Done. You can now run: python3 train/finetune_gemma4.py"
