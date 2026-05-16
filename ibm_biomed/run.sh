#!/usr/bin/env bash
# IBM MAMMAL API — service manager for dlyog03
# Usage: bash run.sh start | stop | restart | status | log

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"
PID_FILE="$SCRIPT_DIR/mammal.pid"
LOG_FILE="$SCRIPT_DIR/mammal_api.log"
PORT=8090
CMD="python serve_mammal.py"

_pid() {
    [ -f "$PID_FILE" ] && cat "$PID_FILE" || echo ""
}

_running() {
    local pid; pid=$(_pid)
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

do_start() {
    if _running; then
        echo "Already running (PID $(_pid)). Use 'restart' to reload."
        exit 0
    fi
    if [ ! -f "$VENV/bin/activate" ]; then
        echo "ERROR: venv not found at $VENV — run setup.sh first."
        exit 1
    fi
    echo "Starting IBM MAMMAL API on port $PORT ..."
    cd "$SCRIPT_DIR"
    source "$VENV/bin/activate"
    nohup $CMD >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "PID=$(cat $PID_FILE) — waiting for model load ..."
    sleep 8
    if _running; then
        local health; health=$(curl -sf "http://localhost:$PORT/health" 2>/dev/null || echo "")
        if echo "$health" | grep -q '"ready"'; then
            echo "MAMMAL API ready."
            echo "$health" | python3 -m json.tool 2>/dev/null || echo "$health"
        else
            echo "Process running but /health not ready yet — check: bash run.sh log"
        fi
    else
        echo "ERROR: Process died on startup. Check: bash run.sh log"
        exit 1
    fi
}

do_stop() {
    if ! _running; then
        echo "Not running."
        rm -f "$PID_FILE"
        return
    fi
    local pid; pid=$(_pid)
    echo "Stopping PID $pid ..."
    kill "$pid"
    for i in $(seq 1 10); do
        _running || break
        sleep 1
    done
    if _running; then
        echo "Graceful stop failed — force killing ..."
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "Stopped. GPU memory freed."
}

do_status() {
    if _running; then
        local pid; pid=$(_pid)
        echo "RUNNING (PID $pid)"
        local health; health=$(curl -sf "http://localhost:$PORT/health" 2>/dev/null || echo "")
        if [ -n "$health" ]; then
            echo "$health" | python3 -m json.tool 2>/dev/null || echo "$health"
        else
            echo "WARNING: Process running but /health not responding on port $PORT"
        fi
    else
        echo "STOPPED"
        rm -f "$PID_FILE"
    fi
}

do_log() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "No log file yet: $LOG_FILE"
        exit 1
    fi
    echo "=== $LOG_FILE (Ctrl+C to stop) ==="
    tail -f "$LOG_FILE"
}

case "${1:-}" in
    start)   do_start   ;;
    stop)    do_stop    ;;
    restart) do_stop; sleep 2; do_start ;;
    status)  do_status  ;;
    log)     do_log     ;;
    *)
        echo "Usage: bash run.sh start | stop | restart | status | log"
        exit 1
        ;;
esac
