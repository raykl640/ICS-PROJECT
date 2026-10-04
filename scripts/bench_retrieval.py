#!/usr/bin/env python
"""Retrieval latency per stage, e.g. `python scripts/bench_retrieval.py -n 50`.

--fake runs on the synthetic test corpus with the fake embedder and reranker (no models, no built indexes).
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.config import Settings
from backend.app.retrieval.bench import main

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--fake" not in args:
        raise SystemExit(main(args))
    args.remove("--fake")
    from backend.tests.fake_pipeline import fake_pipeline

    with tempfile.TemporaryDirectory() as tmp:
        raise SystemExit(main(args, pipeline=fake_pipeline(Path(tmp), Settings(relevance_threshold=1.0))))
