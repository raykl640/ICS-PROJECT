"""Generation latency: time to first token and total time per answer, with the machine it ran on.

Each run retrieves context, builds the real prompt and streams it from the LLM. The first run is reported separately
as cold (Ollama may still be loading the model); warm runs give the p50/p95. Questions whose retrieval is null are
skipped (no generation happens for them). CLI: python eval/bench_latency.py [-n RUNS]
"""

import argparse
import asyncio
import sys
import time
from collections.abc import Sequence
from typing import Any

from backend.app.config import Settings, get_settings
from backend.app.evaluation.common import use_offline_models, write_json
from backend.app.generation.llm import OllamaClient, OllamaError
from backend.app.generation.prompt import build_prompt
from backend.app.interfaces import LLMClient
from backend.app.retrieval.bench import DEFAULT_QUERIES, percentile, platform_info
from backend.app.retrieval.meta import IndexMismatchError
from backend.app.retrieval.pipeline import ContextPipeline, ContextResult, load_pipeline


async def time_stream(llm: LLMClient, prompt: str) -> tuple[float | None, float, int]:
    """(seconds to first token, total seconds, token count) for one streamed generation."""
    start = time.perf_counter()
    first: float | None = None
    tokens = 0
    async for _ in llm.stream(prompt):
        if first is None:
            first = time.perf_counter() - start
        tokens += 1
    return first, time.perf_counter() - start, tokens


def answerable(pipeline: ContextPipeline, questions: Sequence[str]) -> list[tuple[str, ContextResult]]:
    """(question, reranked chunks) for every question that is not null."""
    out = []
    for question in questions:
        result = pipeline.retrieve_context(question)
        if not result.null:
            out.append((question, result))
    return out


async def run_latency(
    pipeline: ContextPipeline, llm: LLMClient, questions: Sequence[str], runs: int, settings: Settings
) -> list[dict[str, Any]]:
    """`runs` timed generations cycling through the answerable questions (ValueError if none is answerable)."""
    usable = answerable(pipeline, questions)
    if not usable:
        raise ValueError("every benchmark question was null; nothing to generate")
    results = []
    for n in range(runs):
        question, context = usable[n % len(usable)]
        prompt = build_prompt(question, [c.chunk for c in context.chunks], settings)
        ttft, total, tokens = await time_stream(llm, prompt.text)
        results.append(
            {
                "run": n + 1,
                "cold": n == 0,
                "question_index": questions.index(question),
                "retrieval_ms": context.debug.timings_ms["total"],
                "ttft_s": ttft,
                "total_s": total,
                "tokens": tokens,
                "tokens_per_s": tokens / total if total else 0.0,
            }
        )
    return results


def summarize(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Cold run, and p50/p95 of TTFT and total over the warm runs (all runs when there is only one)."""
    warm = [r for r in runs if not r["cold"]] or list(runs)
    out: dict[str, Any] = {"cold": runs[0] if runs else None, "warm_runs": len(warm)}
    for key in ("ttft_s", "total_s", "tokens_per_s"):
        values = [r[key] for r in warm if r[key] is not None]
        out[key] = {"p50": percentile(values, 0.5), "p95": percentile(values, 0.95)} if values else None
    return out


def render(result: dict[str, Any]) -> str:
    """Hardware block and latency lines."""
    lines = [f"{k}: {v}" for k, v in result["hardware"].items()]
    s = result["summary"]
    cold = s["cold"]
    if cold:
        ttft = f"{cold['ttft_s']:.1f}" if cold["ttft_s"] is not None else "-"
        lines.append(f"cold run: first token {ttft} s, total {cold['total_s']:.1f} s, {cold['tokens']} tokens")
    for key, label in (("ttft_s", "first token"), ("total_s", "total"), ("tokens_per_s", "tokens/s")):
        if s[key]:
            lines.append(f"warm {label} (n={s['warm_runs']}): p50 {s[key]['p50']:.1f}, p95 {s[key]['p95']:.1f}")
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
    settings: Settings | None = None,
    pipeline: ContextPipeline | None = None,
    llm: LLMClient | None = None,
) -> int:
    """CLI. 0 on success, 1 when the LLM fails or nothing is answerable, 2 when the indexes are missing/stale."""
    parser = argparse.ArgumentParser(description="Benchmark LLM time to first token and total generation time.")
    parser.add_argument("-n", "--runs", type=int, default=4, help="timed generations, the first one cold (default 4)")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    if pipeline is None:
        try:
            use_offline_models()
            pipeline = load_pipeline(settings)
        except (IndexMismatchError, FileNotFoundError) as err:
            print(err, file=sys.stderr)
            return 2
    llm = llm or OllamaClient(settings)
    try:
        runs = asyncio.run(run_latency(pipeline, llm, DEFAULT_QUERIES, args.runs, settings))
    except (OllamaError, ValueError) as err:
        print(f"latency benchmark failed: {err}", file=sys.stderr)
        return 1
    hardware = platform_info() | {
        "llm_model": settings.ollama_model,
        "num_ctx": str(settings.num_ctx),
        "num_predict": str(settings.num_predict),
    }
    result = {"hardware": hardware, "summary": summarize(runs), "runs": runs}
    write_json(settings.eval_results_dir / "latency.json", result)
    print(render(result))
    return 0
