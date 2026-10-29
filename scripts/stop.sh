#!/usr/bin/env bash

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="$ROOT_DIR/logs"

for pidfile in "$LOGS_DIR/frontend.pid" "$LOGS_DIR/backend.pid" "$LOGS_DIR/ml_service.pid"; do
  if [ -f "$pidfile" ]; then
    PID=$(cat "$pidfile")
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
      echo "Stopping PID $PID..."
      kill "$PID" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
done

echo "All registered BESS Optimizer processes stopped."
