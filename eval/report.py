#!/usr/bin/env python
"""Assemble eval/report.md from eval/results/."""

import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parents[1])  # repo root instead of eval/, so imports resolve as in the app

from backend.app.evaluation.report import main

if __name__ == "__main__":
    raise SystemExit(main())
