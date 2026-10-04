#!/usr/bin/env python
"""One-time online setup for offline runs: cache the four Hugging Face models and pull the Ollama model.

Usage: `python scripts/setup_offline.py [--skip-ollama]`. Model names come from backend/app/config.py.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from huggingface_hub import snapshot_download

from backend.app.config import get_settings


def main(argv: list[str] | None = None) -> int:
    """Download every configured model into the local caches; 1 if Ollama is missing."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-ollama", action="store_true", help="only cache the Hugging Face models")
    args = parser.parse_args(argv)
    s = get_settings()
    for model in (s.embedding_model, s.reranker_model, s.translator_sw_en, s.translator_en_sw):
        print(f"caching {model}")
        snapshot_download(model)
    if args.skip_ollama:
        return 0
    if shutil.which("ollama") is None:
        print(f"ollama is not installed; install it, then run: ollama pull {s.ollama_model}", file=sys.stderr)
        return 1
    subprocess.run(["ollama", "pull", s.ollama_model], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
