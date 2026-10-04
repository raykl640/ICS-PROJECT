#!/usr/bin/env python
"""Time to first token and total generation time on this machine (needs Ollama and the indexes)."""

import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parents[1])  # repo root instead of eval/, so imports resolve as in the app

from backend.app.evaluation.latency import main

if __name__ == "__main__":
    raise SystemExit(main())
