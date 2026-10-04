#!/usr/bin/env python
"""One-time online setup for offline runs: cache the four Hugging Face models, pull the Ollama model, build chunks and
indexes, then verify everything loads with HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 (backend/app/offline.py).

Usage: `python scripts/setup_offline.py [--skip-ollama] [--skip-index] [--verify-only]`. Models come from config.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.offline import main

if __name__ == "__main__":
    raise SystemExit(main())
