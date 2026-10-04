"""Retrieval latency benchmark: p50/p95 per stage over N queries, plus platform info for the report.

CLI: python scripts/bench_retrieval.py [-n N] [--queries FILE] [--fake]
"""

import argparse
import math
import os
import platform
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from backend.app.config import Settings, get_settings
from backend.app.retrieval.meta import IndexMismatchError
from backend.app.retrieval.pipeline import ContextPipeline, load_pipeline

# Handwritten lay questions covering the corpus domains (not statute text).
DEFAULT_QUERIES: tuple[str, ...] = (
    "my employer fired me without notice",
    "my landlord wants to evict me from my house",
    "I was arrested and held for three days without being taken to court",
    "the shop refused to refund me for a faulty phone",
    "what does section 41 of the Employment Act say",
    "can the police search my car without a warrant",
    "my landlord increased the rent without telling me",
    "the government wants to take my land for a road",
    "how many days of annual leave am I entitled to",
    "can I get free legal help if I cannot afford a lawyer",
)
STAGES: tuple[str, ...] = ("route", "embed", "dense", "sparse", "rrf", "rerank", "total")


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile (p in (0, 1]); the smallest value with at least p of the data at or below it."""
    if not values:
        raise ValueError("percentile of an empty sequence")
    ordered = sorted(values)
    return ordered[max(math.ceil(p * len(ordered)), 1) - 1]


def summarize(runs: Sequence[dict[str, float]]) -> dict[str, tuple[float, float]]:
    """(p50, p95) in ms for every stage that appears in the runs."""
    stages = dict.fromkeys(stage for run in runs for stage in run)
    return {s: (percentile(v, 0.5), percentile(v, 0.95)) for s in stages if (v := [r[s] for r in runs if s in r])}


def _cpu_model() -> str:
    """CPU model name from /proc/cpuinfo (Linux), else whatever platform reports."""
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def _ram_gb() -> str:
    """Physical RAM in GiB where the OS exposes it via sysconf."""
    try:
        return f"{os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2**30:.1f} GiB"
    except (AttributeError, ValueError, OSError):
        return "unknown"


def platform_info() -> dict[str, str]:
    """Python, OS, CPU model, logical cores and RAM of this machine."""
    return {
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": _cpu_model(),
        "cores": str(os.cpu_count() or "unknown"),
        "ram": _ram_gb(),
    }


def run_bench(pipeline: ContextPipeline, queries: Sequence[str], runs: int) -> tuple[list[dict[str, float]], int]:
    """One untimed warm-up query, then `runs` queries cycling through `queries`; returns timings and null count."""
    pipeline.retrieve_context(queries[0])
    timings, nulls = [], 0
    for i in range(runs):
        result = pipeline.retrieve_context(queries[i % len(queries)])
        timings.append(result.debug.timings_ms)
        nulls += result.null
    return timings, nulls


def render(stats: dict[str, tuple[float, float]], info: dict[str, str], runs: int, nulls: int, load_ms: float) -> str:
    """Platform block and a per-stage p50/p95 table (dense and sparse run in parallel, so stages do not sum)."""
    lines = [f"{key}: {value}" for key, value in info.items()]
    lines += [
        f"load: {load_ms:.0f} ms",
        f"runs: {runs}",
        f"null: {nulls}/{runs}",
        f"{'stage':<8}{'p50 ms':>10}{'p95 ms':>10}",
    ]
    lines += [f"{s:<8}{stats[s][0]:>10.1f}{stats[s][1]:>10.1f}" for s in STAGES if s in stats]
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None, settings: Settings | None = None, pipeline: ContextPipeline | None = None
) -> int:
    """CLI. Exit 0 on success, 2 when chunks.json or the indexes are missing or stale."""
    parser = argparse.ArgumentParser(description="Benchmark retrieval latency per stage.")
    parser.add_argument("-n", "--runs", type=int, default=20, help="number of timed queries (default 20)")
    parser.add_argument("--queries", type=Path, help="file with one query per line (default: built-in set)")
    args = parser.parse_args(argv)
    queries = DEFAULT_QUERIES
    if args.queries:
        queries = tuple(q for line in args.queries.read_text(encoding="utf-8").splitlines() if (q := line.strip()))
    start = time.perf_counter()
    if pipeline is None:
        try:
            pipeline = load_pipeline(settings or get_settings())
        except (IndexMismatchError, FileNotFoundError) as err:
            print(err, file=sys.stderr)
            return 2
    load_ms = (time.perf_counter() - start) * 1000
    timings, nulls = run_bench(pipeline, queries, args.runs)
    print(render(summarize(timings), platform_info(), args.runs, nulls, load_ms))
    return 0
