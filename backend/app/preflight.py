"""Pre-run checks for scripts/run.sh and run.ps1: Ollama and its model, chunks and indexes, the frontend build.

`python -m backend.app.preflight` prints each problem with its fix; exit 0 ready, 3 only Ollama is down (the run
script may start it and retry), 1 anything else. `--address` prints "HOST PORT" from config.py.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from backend.app.config import Settings, get_settings
from backend.app.generation.llm import OllamaClient
from backend.app.retrieval.meta import IndexMismatchError, read_meta
from backend.app.retrieval.store import ChunkStore

EXIT_OK = 0
EXIT_NOT_READY = 1
EXIT_OLLAMA_DOWN = 3
CORPUS_COMMAND = "python -m backend.app.ingestion.build_corpus"
FRONTEND_COMMAND = "cd frontend && npm ci && npm run build"


def index_problems(settings: Settings) -> list[str]:
    """chunks.json readable and both indexes built for it (and for the configured embedding model)."""
    try:
        store = ChunkStore.load(settings.chunks_path)
    except (OSError, ValueError):
        return [f"{settings.chunks_path} is missing or invalid (build it: {CORPUS_COMMAND})"]
    try:
        read_meta(settings.dense_index_dir, "dense", store.corpus_hash, settings.embedding_model)
        read_meta(settings.sparse_index_dir, "sparse", store.corpus_hash)
    except IndexMismatchError as exc:
        return [str(exc)]
    return []


def check(settings: Settings, status: tuple[bool, bool]) -> tuple[int, list[str]]:
    """(exit code, problems) given Ollama's (reachable, model present)."""
    reachable, present = status
    problems = index_problems(settings)
    if not (settings.frontend_dist / "index.html").is_file():
        problems.append(f"the frontend is not built (build it: {FRONTEND_COMMAND})")
    if reachable and not present:
        problems.append(f"the model is not in Ollama (run: ollama pull {settings.ollama_model})")
    code = EXIT_NOT_READY if problems else EXIT_OK if reachable else EXIT_OLLAMA_DOWN
    if not reachable:
        problems.insert(0, f"Ollama is not reachable at {settings.ollama_url} (start it: ollama serve)")
    return code, problems


def main(argv: Sequence[str] | None = None, status: tuple[bool, bool] | None = None) -> int:
    """CLI; `status` replaces the live Ollama check in tests."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--address", action="store_true", help='print "HOST PORT" of the API and exit')
    args = parser.parse_args(argv)
    settings = get_settings()
    if args.address:
        print(settings.api_host, settings.api_port)
        return EXIT_OK
    code, problems = check(settings, status or asyncio.run(OllamaClient(settings).status()))
    for problem in problems:
        print(f"not ready: {problem}", file=sys.stderr)
    if code == EXIT_OK:
        print("ready: Ollama, model, indexes and frontend")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
