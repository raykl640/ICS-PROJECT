#!/usr/bin/env bash
# Local + CI gate: lint, format, types, tests with coverage. Tests use fakes only (no models, no Ollama, no network).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python )}"
"$PY" -m ruff check backend eval
"$PY" -m ruff format --check backend eval
"$PY" -m mypy
"$PY" -m pytest -q --cov --cov-report=term
