#!/usr/bin/env bash
# Start HakiAI: build the frontend once, check Ollama (start it if installed but not running), then serve the API and
# the built frontend on one port (host/port from backend/app/config.py, override with HAKI_API_HOST / HAKI_API_PORT).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )}"

if [ ! -f frontend/dist/index.html ]; then
  command -v npm >/dev/null || { echo "frontend/dist is missing and npm is not installed (install Node.js 20+)" >&2; exit 1; }
  (cd frontend && npm ci && npm run build)
fi

status=0
"$PY" -m backend.app.preflight || status=$?
if [ "$status" -eq 3 ] && command -v ollama >/dev/null; then
  mkdir -p data
  echo "starting Ollama in the background (log: data/ollama.log)"
  nohup ollama serve >data/ollama.log 2>&1 &
  for _ in $(seq 1 30); do
    sleep 1
    status=0
    "$PY" -m backend.app.preflight >/dev/null 2>&1 || status=$?
    [ "$status" -ne 3 ] && break
  done
  [ "$status" -eq 0 ] || "$PY" -m backend.app.preflight || true
fi
[ "$status" -eq 0 ] || exit "$status"

read -r HOST PORT < <("$PY" -m backend.app.preflight --address)
echo "HakiAI is starting on http://$HOST:$PORT (first answers are slow while the model loads; Ctrl+C stops it)"
exec "$PY" -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT"
