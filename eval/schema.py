#!/usr/bin/env python
"""Print the JSON Schema of eval/ground_truth.json."""

import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parents[1])  # repo root instead of eval/, so imports resolve as in the app

from backend.app.evaluation.schema import schema_main

if __name__ == "__main__":
    raise SystemExit(schema_main())
