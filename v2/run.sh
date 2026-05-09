#!/usr/bin/env bash
# run.sh — Deep2Lead V2 service manager
# Usage: ./run.sh [start|stop|restart|status|log|tail|setup]

set -euo pipefail
cd "$(dirname "$0")"

# ── Config ────────────────────────────────────────────────────────
APP_DIR="$(pwd)"
VENV_DIR="$APP_DIR/.venv"
PID_FILE="$APP_DIR/.gunicorn.pid"
LOG_FILE="$APP_DIR/logs/app.log"
PORT=5018
WORKERS=2
TIMEOUT=120

# ── Helpers ───────────────────────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

activate_venv() {
  [ -f "$VENV_DIR/bin/activate" ] || die "Virtual env not found. Run: ./run.sh setup"
  source "$VENV_DIR/bin/activate"
  export PYTHONPATH="$APP_DIR"
  [ -f "$APP_DIR/.env" ] && set -a && source "$APP_DIR/.env" && set +a
}

is_running() {
  [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

# ── Commands ──────────────────────────────────────────────────────

cmd_setup() {
  log "Creating virtual environment at $VENV_DIR …"
  python3 -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"

  log "Installing dependencies …"
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
  log "Dependencies installed."

  mkdir -p logs

  if [ ! -f .env ]; then
    cp .env.example .env
    log "Created .env from .env.example — edit it before starting."
  fi

  log "Running database migrations …"
  export PYTHONPATH="$APP_DIR"
  set -a && source .env && set +a

  if [ ! -d migrations ]; then
    flask --app "app:create_app" db init
  fi
  flask --app "app:create_app" db migrate -m "auto" 2>/dev/null || true
  flask --app "app:create_app" db upgrade

  log ""
  log "Setup complete. Next steps:"
  log "  1. Edit .env with your settings"
  log "  2. ./run.sh start"
  log "  3. ./run.sh create-admin <username> <password>"
}

cmd_start() {
  if is_running; then
    log "Already running (PID $(cat "$PID_FILE")). Use restart to reload."
    exit 0
  fi

  activate_venv
  mkdir -p logs

  log "Running database migrations …"
  flask --app "app:create_app" db upgrade

  log "Starting gunicorn on port $PORT …"
  gunicorn "app:create_app()" \
    --bind "0.0.0.0:$PORT" \
    --workers "$WORKERS" \
    --timeout "$TIMEOUT" \
    --pid "$PID_FILE" \
    --access-logfile "$LOG_FILE" \
    --error-logfile "$LOG_FILE" \
    --capture-output \
    --daemon

  sleep 1
  if is_running; then
    log "Started. PID $(cat "$PID_FILE") · http://localhost:$PORT"
  else
    die "Failed to start — check logs: ./run.sh tail"
  fi
}

cmd_stop() {
  if ! is_running; then
    log "Not running."
    rm -f "$PID_FILE"
    exit 0
  fi
  local pid
  pid=$(cat "$PID_FILE")
  log "Stopping PID $pid …"
  kill -TERM "$pid"
  for i in $(seq 1 10); do
    is_running || break
    sleep 1
  done
  is_running && kill -KILL "$pid" || true
  rm -f "$PID_FILE"
  log "Stopped."
}

cmd_restart() {
  cmd_stop
  sleep 1
  cmd_start
}

cmd_status() {
  if is_running; then
    log "Running · PID $(cat "$PID_FILE") · http://localhost:$PORT"
  else
    log "Not running."
  fi
}

cmd_log() {
  [ -f "$LOG_FILE" ] || die "No log file at $LOG_FILE"
  less +G "$LOG_FILE"
}

cmd_tail() {
  mkdir -p logs
  touch "$LOG_FILE"
  log "Tailing $LOG_FILE (Ctrl-C to stop) …"
  tail -f "$LOG_FILE"
}

cmd_create_admin() {
  [ $# -ge 2 ] || die "Usage: ./run.sh create-admin <username> <password>"
  activate_venv
  flask --app "app:create_app" create-admin "$1" "$2"
}

# ── Dispatch ──────────────────────────────────────────────────────
COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
  setup)        cmd_setup ;;
  start)        cmd_start ;;
  stop)         cmd_stop ;;
  restart)      cmd_restart ;;
  status)       cmd_status ;;
  log)          cmd_log ;;
  tail)         cmd_tail ;;
  create-admin) cmd_create_admin "$@" ;;
  help|--help|-h)
    echo ""
    echo "  Deep2Lead V2 — service manager"
    echo ""
    echo "  Usage: ./run.sh <command>"
    echo ""
    echo "  Commands:"
    echo "    setup          Create .venv, install deps, run DB migrations"
    echo "    start          Start gunicorn in background"
    echo "    stop           Stop gunicorn"
    echo "    restart        Stop then start"
    echo "    status         Show running status"
    echo "    log            Open full log in less"
    echo "    tail           Live-tail the log"
    echo "    create-admin   Create an admin account"
    echo "                   Usage: ./run.sh create-admin <username> <password>"
    echo ""
    ;;
  *) die "Unknown command '$COMMAND'. Run ./run.sh help" ;;
esac
