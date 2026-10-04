#!/usr/bin/env bash
# Local + CI check: backend tests run with fakes only (no model downloads, no Ollama).
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest backend/tests -q -x
