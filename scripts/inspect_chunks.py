#!/usr/bin/env python
"""Print reproducible chunk samples for human review, e.g. `python scripts/inspect_chunks.py --per-act 20`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.ingestion.sample import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
