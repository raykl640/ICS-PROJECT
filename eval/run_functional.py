#!/usr/bin/env python
"""Run eval/queries_functional.json end to end against a running API (`uvicorn backend.app.main:app`)."""

import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parents[1])  # repo root instead of eval/, so imports resolve as in the app

from backend.app.evaluation.functional import main

if __name__ == "__main__":
    raise SystemExit(main())
