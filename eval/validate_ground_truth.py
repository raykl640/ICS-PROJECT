#!/usr/bin/env python
"""Validate eval/ground_truth.json against the chunk store: `python eval/validate_ground_truth.py [FILE]`."""

import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parents[1])  # repo root instead of eval/, so imports resolve as in the app

from backend.app.evaluation.schema import validate_main

if __name__ == "__main__":
    raise SystemExit(validate_main())
