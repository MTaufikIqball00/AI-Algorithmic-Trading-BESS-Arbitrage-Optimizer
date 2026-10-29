#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="$ROOT_DIR/logs"
mkdir -p "$LOGS_DIR"

ML_PID_FILE="$LOGS_DIR/ml_service.pid"
BACKEND_PID_FILE="$LOGS_DIR/backend.pid"
FRONTEND_PID_FILE="$LOGS_DIR/frontend.pid"

echo "=========================================================="
echo "  AI ALGORITHMIC TRADING & BESS ARBITRAGE OPTIMIZER      "
echo "=========================================================="

echo "[1/4] Checking prerequisites..."
command -v cargo >/dev/null 2>&1 || { echo "Cargo required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node required"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python3 required"; exit 1; }

echo "[2/4] Starting Python ML Service (port 8231)..."
(cd "$ROOT_DIR/ml_service" && python3 -m uvicorn service:app --host 127.0.0.1 --port 8231 > "$LOGS_DIR/ml_service.log" 2>&1) &
echo $! > "$ML_PID_FILE"

echo "[3/4] Starting Rust Control Plane API (port 8230)..."
(cd "$ROOT_DIR/backend" && cargo run > "$LOGS_DIR/backend.log" 2>&1) &
echo $! > "$BACKEND_PID_FILE"

echo "[4/4] Starting Frontend Dev Server (port 3230)..."
(cd "$ROOT_DIR/frontend" && npm run dev > "$LOGS_DIR/frontend.log" 2>&1) &
echo $! > "$FRONTEND_PID_FILE"

echo ""
echo "=========================================================="
echo "  SERVICES LAUNCHED IN BACKGROUND                        "
echo "=========================================================="
echo "  Frontend Trading Terminal : http://localhost:3230"
echo "  Rust Control Plane API    : http://localhost:8230/api/health"
echo "  Python ML Engine (XGB/PPO): http://localhost:8231/health"
echo "=========================================================="
echo "To stop: ./scripts/stop.sh"
