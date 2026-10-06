"""One-time online setup for offline runs (scripts/setup_offline.py).

Caches the four Hugging Face models (default HF cache, or $HF_HOME), pulls the Ollama model, builds chunks.json (if
missing) and the indexes, then verifies in a fresh process that everything loads with HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1. `--offline-check` is that verification process.
"""

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

from backend.app.config import Settings, get_settings
from backend.app.deps import Deps, real_deps, warm_up
from backend.app.retrieval.meta import IndexMismatchError

ROOT = Path(__file__).resolve().parents[2]
OFFLINE_ENV = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
# Weight formats the PyTorch loaders never read; skipping them saves hundreds of MB per model.
UNUSED_MODEL_FILES = (
    "onnx/*",
    "openvino/*",
    "*.onnx",
    "*.h5",
    "*.msgpack",
    "*.ot",
    "*.tflite",
    "tf_model*",
    "flax_model*",
)
_CORPUS_MODULE = "backend.app.ingestion.build_corpus"
_INDEX_MODULE = "backend.app.ingestion.build_index"
_SELF_MODULE = "backend.app.offline"

Runner = Callable[[Sequence[str], Mapping[str, str] | None], int]


@dataclass(frozen=True)
class Step:
    """Outcome of one setup step; detail says what failed and how to fix it."""

    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class Tools:
    """Side effects of the setup, injectable for tests."""

    download: Callable[[str], object]
    which: Callable[[str], str | None]
    run: Runner


def _run(command: Sequence[str], env: Mapping[str, str] | None) -> int:
    """Run a command from the repository root, output passed through; returns its exit code."""
    return subprocess.run(list(command), env=dict(env) if env is not None else None, cwd=ROOT, check=False).returncode


def _download(model: str) -> object:
    """Cache a Hugging Face model without its unused ONNX/OpenVINO/TF/Flax/Rust variants (imported here so
    --offline-check never loads the hub client)."""
    from huggingface_hub import snapshot_download

    return snapshot_download(model, ignore_patterns=list(UNUSED_MODEL_FILES))


def real_tools() -> Tools:
    """Hugging Face download, PATH lookup and subprocess."""
    return Tools(download=_download, which=shutil.which, run=_run)


def hf_models(settings: Settings) -> tuple[str, ...]:
    """Embedder, cross-encoder and both Marian translators."""
    return (settings.embedding_model, settings.reranker_model, settings.translator_sw_en, settings.translator_en_sw)


def cache_models(models: Sequence[str], download: Callable[[str], object]) -> list[Step]:
    """Download each model into the local cache; a failure is reported and the rest still run."""
    steps = []
    for model in models:
        try:
            download(model)
        except (OSError, httpx.HTTPError) as exc:
            steps.append(Step(f"cache {model}", False, f"{type(exc).__name__}: {exc}"))
        else:
            steps.append(Step(f"cache {model}", True))
    return steps


def pull_ollama(model: str, tools: Tools) -> Step:
    """`ollama pull <model>`, or the command to run once Ollama is installed."""
    name = f"ollama pull {model}"
    if tools.which("ollama") is None:
        return Step(name, False, f"Ollama is not installed; install it (https://ollama.com), then run: {name}")
    if tools.run(["ollama", "pull", model], None) != 0:
        return Step(name, False, f"the pull failed; check that Ollama is running (ollama serve), then run: {name}")
    return Step(name, True)


def _module(module: str, *args: str) -> list[str]:
    """`python -m module args` with this interpreter."""
    return [sys.executable, "-m", module, *args]


def build_data(settings: Settings, tools: Tools) -> list[Step]:
    """build_corpus when chunks.json is missing, then build_index; stops at the first failure."""
    commands = [] if settings.chunks_path.exists() else [("build corpus", _CORPUS_MODULE)]
    commands.append(("build indexes", _INDEX_MODULE))
    steps = []
    for name, module in commands:
        ok = tools.run(_module(module), None) == 0
        steps.append(Step(name, ok, "" if ok else f"see the output above; rerun: python -m {module}"))
        if not ok:
            break
    return steps


def verify_in_fresh_process(tools: Tools, check_ollama: bool) -> Step:
    """Rerun this module with --offline-check under HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 (read at import time)."""
    args = ["--offline-check"] + ([] if check_ollama else ["--skip-ollama"])
    ok = tools.run(_module(_SELF_MODULE, *args), {**os.environ, **OFFLINE_ENV}) == 0
    return Step("offline verification", ok, "" if ok else "a component did not load offline (see the lines above)")


def verify_offline(deps: Deps, check_ollama: bool) -> list[Step]:
    """Load indexes and every local model, warm them, and (optionally) check the Ollama model is present."""
    try:
        pipeline = deps.load_pipeline()
    except (IndexMismatchError, OSError, ValueError) as exc:
        return [Step("load indexes and retrieval models", False, f"{type(exc).__name__}: {exc}")]
    steps = [Step("load indexes and retrieval models", True)]
    try:
        warm_up(pipeline, deps.language)
    except OSError as exc:
        return [*steps, Step("warm up embedder, cross-encoder and translators", False, f"{type(exc).__name__}: {exc}")]
    steps.append(Step("warm up embedder, cross-encoder and translators", True))
    if check_ollama:
        reachable, present = asyncio.run(deps.llm.status())
        model = deps.settings.ollama_model
        detail = "" if present else ("start it: ollama serve" if not reachable else f"run: ollama pull {model}")
        steps.append(Step("ollama model available", present, detail))
    return steps


def report(steps: Sequence[Step]) -> int:
    """Print one line per step; 0 when all passed."""
    for step in steps:
        print(f"OK   {step.name}" if step.ok else f"FAIL {step.name}: {step.detail}")
    return 0 if all(step.ok for step in steps) else 1


def _setup(args: argparse.Namespace, settings: Settings, tools: Tools) -> list[Step]:
    """Download, pull and build (each unless skipped), then verify if the builds succeeded."""
    steps: list[Step] = []
    if not args.verify_only:
        steps += cache_models(hf_models(settings), tools.download)
        if not args.skip_ollama:
            steps.append(pull_ollama(settings.ollama_model, tools))
        if not args.skip_index:
            built = build_data(settings, tools)
            steps += built
            if not all(step.ok for step in built):
                return steps
    steps.append(verify_in_fresh_process(tools, check_ollama=not args.skip_ollama))
    return steps


def main(argv: Sequence[str] | None = None, *, tools: Tools | None = None, deps: Deps | None = None) -> int:
    """CLI; exit 0 when every step passed, 1 otherwise (each failure line names its fix)."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--skip-ollama", action="store_true", help="neither pull nor check the Ollama model")
    parser.add_argument("--skip-index", action="store_true", help="do not (re)build chunks.json and the indexes")
    parser.add_argument("--verify-only", action="store_true", help="only check that everything loads offline")
    parser.add_argument("--offline-check", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    settings = get_settings()
    if args.offline_check:
        return report(verify_offline(deps or real_deps(settings), check_ollama=not args.skip_ollama))
    return report(_setup(args, settings, tools or real_tools()))


if __name__ == "__main__":
    raise SystemExit(main())
