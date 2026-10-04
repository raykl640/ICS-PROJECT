#!/usr/bin/env python
"""Blank rating sheets (one CSV per rater) and responses.md from eval/results/functional.json."""

import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parents[1])  # repo root instead of eval/, so imports resolve as in the app

from backend.app.evaluation.rating import make_sheets_main

if __name__ == "__main__":
    raise SystemExit(make_sheets_main())
