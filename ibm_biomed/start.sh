#!/usr/bin/env bash
# Start IBM MAMMAL API in a detached screen session on dlyog03.
# Run from: /home/dlyog/apps/ibm_biomed/
# Prerequisite: setup.sh must have been run first.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"
PORT=8090

if [[ ! -f "$VENV/bin/activate" ]]; then
    echo "ERROR: venv not found at $VENV"
    echo "Run setup.sh first."
    exit 1
fi

# Kill any existing session
screen -S mammal_api -X quit 2>/dev/null || true
sleep 1

echo "Starting IBM MAMMAL API (port $PORT) in screen session 'mammal_api' ..."
screen -dmS mammal_api bash -c "
    cd $SCRIPT_DIR
    source $VENV/bin/activate
    python serve_mammal.py 2>&1 | tee mammal_api.log
"

sleep 3
if screen -list | grep -q mammal_api; then
    echo "Screen session 'mammal_api' is running."
    echo ""
    echo "Monitor: tail -f $SCRIPT_DIR/mammal_api.log"
    echo "Health:  curl http://localhost:$PORT/health"
    echo "Stop:    screen -S mammal_api -X quit"
else
    echo "ERROR: screen session failed to start. Check mammal_api.log"
    exit 1
fi
