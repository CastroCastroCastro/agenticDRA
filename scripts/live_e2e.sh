#!/usr/bin/env bash
# Live E2E: Postgres (Docker) → seed → DRA gRPC server → connect_check + run_machine_stats.
# Requires: docker compose up -d, repo .venv with requirements installed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
PY="${ROOT}/.venv/bin/python"
export METADATA_DB_URL="${METADATA_DB_URL:-postgresql://postgres:postgres@localhost:5433/machines_db}"

if [[ ! -x "$PY" ]]; then
  echo "No .venv found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

cleanup() {
  pkill -f "agent/run_dra_server.py" 2>/dev/null || true
}
trap cleanup EXIT

"$PY" agent/seed_dev_machine.py
"$PY" agent/run_dra_server.py &
sleep 2
echo "=== run_connect_check ==="
"$PY" agent/run_connect_check.py
echo "=== run_machine_stats ==="
"$PY" agent/run_machine_stats.py
echo "=== run_deploy_rpc_demo (DeployApp stub) ==="
"$PY" agent/run_deploy_rpc_demo.py
if "$PY" -c "import sys; from agent.env import get_openai_api_key; sys.exit(0 if get_openai_api_key() else 1)"; then
  echo "=== run_openai_connect (OPENAI_API_KEY set) ==="
  "$PY" agent/run_openai_connect.py "pick a reachable machine for gRPC" || echo "WARNING: OpenAI connect failed (check key, model, or network)"
else
  echo "=== run_openai_connect (skipped — set OPENAI_API_KEY in .env to enable) ==="
fi
echo "=== done ==="
