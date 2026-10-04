"""Null-response threshold sweep (ARCHITECTURE.md §7.5): in-corpus ground-truth questions vs out-of-corpus ones.

A question goes null when fewer than min_confident_chunks reranked chunks score >= relevance_threshold, i.e. when its
k-th best score (k = min_confident_chunks) is below the threshold. The positive class is "should be null"
(out-of-corpus). The recommendation maximises F1; ties go to fewer refused in-corpus questions, then the lower value.
It is printed, never written to config. CLI: python eval/tune_threshold.py
"""

import argparse
import itertools
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, TypeAdapter

from backend.app.config import Settings, get_settings
from backend.app.evaluation.common import ToEnglish, marian_to_english, read_json, use_offline_models, write_json
from backend.app.evaluation.schema import load_ground_truth
from backend.app.retrieval.meta import IndexMismatchError
from backend.app.retrieval.pipeline import ContextResult, load_pipeline
from backend.app.retrieval.store import ChunkStore

_ROUND = 3


class OutOfCorpusQuery(BaseModel):
    """A question the corpus cannot answer; the system should return the fixed fallback."""

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)


OUT_OF_CORPUS = TypeAdapter(list[OutOfCorpusQuery])


@dataclass(frozen=True)
class SweepPoint:
    """Confusion counts and scores of the null decision at one threshold."""

    threshold: float
    tp: int  # out-of-corpus -> null
    fp: int  # in-corpus -> null (refused a question the corpus covers)
    fn: int  # out-of-corpus -> answered
    tn: int  # in-corpus -> answered
    precision: float
    recall: float
    f1: float


def kth_score(scores: Sequence[float], k: int) -> float | None:
    """k-th highest score, None when fewer than k chunks were scored (always null)."""
    ordered = sorted(scores, reverse=True)
    return ordered[k - 1] if len(ordered) >= k else None


def _is_null(score: float | None, threshold: float) -> bool:
    """The pipeline's decision for a question whose k-th score is `score`."""
    return score is None or score < threshold


def evaluate(threshold: float, in_scores: Sequence[float | None], out_scores: Sequence[float | None]) -> SweepPoint:
    """Precision/recall/F1 of 'null' at one threshold (0.0 where a ratio is undefined)."""
    tp = sum(_is_null(s, threshold) for s in out_scores)
    fp = sum(_is_null(s, threshold) for s in in_scores)
    fn, tn = len(out_scores) - tp, len(in_scores) - fp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return SweepPoint(threshold, tp, fp, fn, tn, precision, recall, f1)


def candidates(scores: Sequence[float | None]) -> list[float]:
    """Thresholds between every pair of neighbouring observed scores, plus one below and one above all of them."""
    values = sorted({s for s in scores if s is not None})
    if not values:
        return [0.0]
    mids = [(a + b) / 2 for a, b in itertools.pairwise(values)]
    return sorted({round(t, _ROUND) for t in [values[0] - 0.5, *mids, values[-1] + 0.5]})


def sweep(in_scores: Sequence[float | None], out_scores: Sequence[float | None]) -> list[SweepPoint]:
    """The null decision evaluated at every candidate threshold, ascending."""
    return [evaluate(t, in_scores, out_scores) for t in candidates([*in_scores, *out_scores])]


def recommend(points: Sequence[SweepPoint]) -> SweepPoint:
    """Highest F1; ties -> fewer in-corpus questions refused, then the lower threshold."""
    return min(points, key=lambda p: (-p.f1, p.fp, p.threshold))


def collect_scores(
    questions: Sequence[tuple[str, str]], retrieve: Callable[[str], ContextResult], k: int
) -> list[dict[str, Any]]:
    """(id, English question) -> id and k-th rerank score, from the pipeline's debug scores (kept even when null)."""
    return [{"id": qid, "kth_score": kth_score([s for _, s in retrieve(q).debug.scores], k)} for qid, q in questions]


def render(result: dict[str, Any]) -> str:
    """Sweep table plus the current and recommended thresholds."""
    head = f"{'threshold':>10} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4} {'prec':>6} {'recall':>6} {'F1':>6}"
    lines = [f"in-corpus: {result['n_in']}  out-of-corpus: {result['n_out']}  k = {result['k']}", head]
    for p in result["sweep"]:
        lines.append(
            f"{p['threshold']:>10.3f} {p['tp']:>4} {p['fp']:>4} {p['fn']:>4} {p['tn']:>4} "
            f"{p['precision']:>6.2f} {p['recall']:>6.2f} {p['f1']:>6.2f}"
        )
    cur, rec = result["current"], result["recommended"]
    lines += [
        f"current relevance_threshold {cur['threshold']}: F1 {cur['f1']:.2f} (refused in-corpus {cur['fp']}, "
        f"answered out-of-corpus {cur['fn']})",
        f"recommended relevance_threshold = {rec['threshold']} (F1 {rec['f1']:.2f}); set HAKI_RELEVANCE_THRESHOLD or "
        "config.py by hand",
    ]
    return "\n".join(lines)


def tune(in_rows: list[dict[str, Any]], out_rows: list[dict[str, Any]], settings: Settings) -> dict[str, Any]:
    """Sweep result with per-question scores, the current threshold's metrics and the recommendation."""
    ins = [r["kth_score"] for r in in_rows]
    outs = [r["kth_score"] for r in out_rows]
    points = sweep(ins, outs)
    return {
        "k": settings.min_confident_chunks,
        "n_in": len(ins),
        "n_out": len(outs),
        "current": asdict(evaluate(settings.relevance_threshold, ins, outs)),
        "recommended": asdict(recommend(points)),
        "sweep": [asdict(p) for p in points],
        "in_corpus": in_rows,
        "out_of_corpus": out_rows,
    }


def main(
    argv: Sequence[str] | None = None,
    settings: Settings | None = None,
    retrieve: Callable[[str], ContextResult] | None = None,
    to_english: ToEnglish | None = None,
) -> int:
    """CLI. 0 on success, 1 for invalid inputs, 2 when chunks.json or the indexes are missing/stale."""
    parser = argparse.ArgumentParser(description="Sweep relevance_threshold for the null-response decision.")
    parser.add_argument("--out-dir", type=Path, help="default: eval/results")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    try:
        store = ChunkStore.load(settings.chunks_path)
        if retrieve is None:
            use_offline_models()
            retrieve = load_pipeline(settings).retrieve_context
    except (IndexMismatchError, FileNotFoundError) as err:
        print(err, file=sys.stderr)
        return 2
    truth = load_ground_truth(settings.ground_truth_path, store, settings.acts)
    if not truth.ok:
        print(
            "ground truth invalid (see python eval/validate_ground_truth.py):",
            *truth.problems,
            sep="\n  ",
            file=sys.stderr,
        )
        return 1
    to_english = to_english or marian_to_english(settings)
    k = settings.min_confident_chunks
    in_questions = [(r.entry.id, to_english(r.entry.question, r.entry.lang)) for r in truth.entries]
    out_questions = [(q.id, q.question) for q in OUT_OF_CORPUS.validate_python(read_json(settings.out_of_corpus_path))]
    result = tune(collect_scores(in_questions, retrieve, k), collect_scores(out_questions, retrieve, k), settings)
    write_json((args.out_dir or settings.eval_results_dir) / "threshold.json", result)
    print(render(result))
    return 0
