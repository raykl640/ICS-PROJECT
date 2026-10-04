#!/usr/bin/env python
"""Sweep relevance_threshold over in-corpus vs out-of-corpus questions; prints the recommended value."""

import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parents[1])  # repo root instead of eval/, so imports resolve as in the app

from backend.app.evaluation.threshold import main

if __name__ == "__main__":
    raise SystemExit(main())
