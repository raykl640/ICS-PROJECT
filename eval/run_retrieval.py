#!/usr/bin/env python
"""P@5 / Recall@20 / MRR for FAISS, BM25, hybrid and hybrid+rerank on the ground truth (real indexes)."""

import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parents[1])  # repo root instead of eval/, so imports resolve as in the app

from backend.app.evaluation.retrieval_eval import main

if __name__ == "__main__":
    raise SystemExit(main())
