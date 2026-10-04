#!/usr/bin/env python
"""Percent agreement and Fleiss' kappa over eval/ratings/rater_*.csv."""

import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parents[1])  # repo root instead of eval/, so imports resolve as in the app

from backend.app.evaluation.rating import agreement_main

if __name__ == "__main__":
    raise SystemExit(agreement_main())
