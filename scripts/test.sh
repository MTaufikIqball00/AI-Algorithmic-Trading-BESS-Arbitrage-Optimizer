#!/usr/bin/env bash
set -e

echo "=== 1. Checking Rust Code Format & Linter ==="
(cd backend && cargo fmt --check)
(cd backend && cargo clippy --all-targets --all-features -- -D warnings)

echo "=== 2. Running Rust Backend Tests ==="
(cd backend && cargo test)

echo "=== 3. Running Python ML, RL & Solar PV Tests ==="
PYTHONPATH=".:ml_service" pytest ml_service/tests
PYTHONPATH=".:ml_service" pytest solar_pv/tests

echo "=== 4. Checking Frontend TypeScript & Production Build ==="
(cd frontend && npm run build)

echo "=== ALL QUALITY GATES PASSED! ==="
