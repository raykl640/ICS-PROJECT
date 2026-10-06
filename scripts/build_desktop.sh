#!/usr/bin/env bash
# Build the HakiAI desktop app for Linux (D34): dist/HakiAI/ and dist/HakiAI-linux-x86_64.tar.gz (+ .sha256), the file
# scripts/install.sh installs. Needs data/processed/chunks.json; builds the indexes when they are missing or stale
# (downloads the embedding model once), rebuilds the frontend, then runs the packaged app's --self-test.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )}"
NAME="HakiAI-linux-x86_64"

[ -f data/processed/chunks.json ] || {
  echo "data/processed/chunks.json is missing (build it: python -m backend.app.ingestion.build_corpus)" >&2
  exit 1
}
if ! "$PY" -c 'import sys
from backend.app.config import get_settings
from backend.app.preflight import index_problems
sys.exit(1 if index_problems(get_settings()) else 0)'; then
  "$PY" -m backend.app.ingestion.build_index
fi

(cd frontend && { [ -d node_modules ] || npm ci; } && npm run build)
"$PY" -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller desktop/hakiai.spec
cp desktop/icons/hakiai.svg desktop/icons/hakiai.png dist/HakiAI/
dist/HakiAI/HakiAI --self-test

tar -C dist -czf "dist/$NAME.tar.gz" HakiAI
(cd dist && sha256sum "$NAME.tar.gz" >"$NAME.tar.gz.sha256")
echo "built dist/$NAME.tar.gz ($(du -h "dist/$NAME.tar.gz" | cut -f1))"
