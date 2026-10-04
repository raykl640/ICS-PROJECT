"""Retrieval quality on the human ground truth: FAISS-only, BM25-only, hybrid RRF and hybrid + cross-encoder.

P@k uses k = rerank_top (5, what reaches the LLM), Recall@n uses n = top_n (20, what reaches the reranker) and MRR the
whole ranked list. hybrid_rerank reorders all top_n hybrid candidates by cross-encoder score, so its Recall@n equals
hybrid's by construction. CLI: python eval/run_retrieval.py
"""

import argparse
import statistics
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from backend.app.config import Settings, get_settings
from backend.app.evaluation.common import ToEnglish, marian_to_english, use_offline_models, write_json
from backend.app.evaluation.metrics import paired_bootstrap_ci, precision_at_k, recall_at_k, reciprocal_rank
from backend.app.evaluation.schema import ResolvedEntry, load_ground_truth
from backend.app.interfaces import CrossEncoderLike
from backend.app.retrieval.hybrid import RetrievalResult, load_retriever
from backend.app.retrieval.meta import IndexMismatchError
from backend.app.retrieval.reranker import CEReranker, rerank
from backend.app.retrieval.store import ChunkStore

SYSTEMS: tuple[str, ...] = ("faiss", "bm25", "hybrid", "hybrid_rerank")
BASELINES: tuple[str, ...] = ("faiss", "bm25")
FUSED: tuple[str, ...] = ("hybrid", "hybrid_rerank")


class EvalRetriever(Protocol):
    """The three ranked-list modes of HybridRetriever."""

    def retrieve(self, question: str) -> RetrievalResult:
        """Hybrid RRF candidates."""
        ...

    def retrieve_dense_only(self, question: str) -> RetrievalResult:
        """FAISS-only candidates."""
        ...

    def retrieve_sparse_only(self, question: str) -> RetrievalResult:
        """BM25-only candidates."""
        ...


@dataclass(frozen=True)
class Cutoffs:
    """Metric cut-offs and their labels, taken from settings."""

    p_k: int
    recall_k: int

    @property
    def names(self) -> tuple[str, str, str]:
        """Metric labels in table order, e.g. ("P@5", "Recall@20", "MRR")."""
        return f"P@{self.p_k}", f"Recall@{self.recall_k}", "MRR"


def _ids(result: RetrievalResult) -> list[str]:
    """Candidate chunk ids in rank order."""
    return [c.chunk.chunk_id for c in result.candidates]


def ranked_lists(retriever: EvalRetriever, reranker: CrossEncoderLike, question_en: str) -> dict[str, list[str]]:
    """Ranked chunk ids per system for one (English) question."""
    hybrid = retriever.retrieve(question_en)
    reranked = rerank(reranker, question_en, hybrid.candidates, len(hybrid.candidates))
    return {
        "faiss": _ids(retriever.retrieve_dense_only(question_en)),
        "bm25": _ids(retriever.retrieve_sparse_only(question_en)),
        "hybrid": _ids(hybrid),
        "hybrid_rerank": [c.chunk.chunk_id for c in reranked],
    }


def score_ranking(ranked: Sequence[str], relevant: frozenset[str], cut: Cutoffs) -> dict[str, float]:
    """P@k, Recall@n and MRR of one ranked list."""
    p, r, mrr = cut.names
    return {
        p: precision_at_k(ranked, relevant, cut.p_k),
        r: recall_at_k(ranked, relevant, cut.recall_k),
        mrr: reciprocal_rank(ranked, relevant),
    }


def evaluate_queries(
    entries: Sequence[ResolvedEntry],
    rank: Callable[[str], dict[str, list[str]]],
    to_english: ToEnglish,
    cut: Cutoffs,
) -> list[dict[str, Any]]:
    """Per-query rankings (top recall_k ids) and metrics for every system."""
    rows = []
    for item in entries:
        entry = item.entry
        question_en = to_english(entry.question, entry.lang)
        lists = rank(question_en)
        rows.append(
            {
                "id": entry.id,
                "category": entry.category,
                "lang": entry.lang,
                "relevant": sorted(item.relevant_ids),
                "systems": {
                    name: {"ranked": ids[: cut.recall_k], **score_ranking(ids, item.relevant_ids, cut)}
                    for name, ids in lists.items()
                },
            }
        )
    return rows


def _means(rows: Sequence[dict[str, Any]], system: str, metrics: Sequence[str]) -> dict[str, float]:
    """Mean of each metric for one system over the given query rows."""
    return {m: statistics.fmean(row["systems"][system][m] for row in rows) for m in metrics}


def summarize(rows: Sequence[dict[str, Any]], cut: Cutoffs) -> dict[str, Any]:
    """Overall and per-category means per system."""
    categories = sorted({row["category"] for row in rows})
    return {
        system: {
            "mean": _means(rows, system, cut.names),
            "by_category": {
                cat: {"n": len(sub), **_means(sub, system, cut.names)}
                for cat in categories
                if (sub := [row for row in rows if row["category"] == cat])
            },
        }
        for system in SYSTEMS
    }


def compare(
    rows: Sequence[dict[str, Any]], summary: dict[str, Any], cut: Cutoffs, *, resamples: int, seed: int
) -> list[dict[str, Any]]:
    """Paired bootstrap 95% CI of (fused system - best single baseline) per metric; best = higher mean on it."""
    out = []
    for metric in cut.names:
        best = max(BASELINES, key=lambda b: summary[b]["mean"][metric])  # tie -> first listed
        base = [row["systems"][best][metric] for row in rows]
        for system in FUSED:
            values = [row["systems"][system][metric] for row in rows]
            diff, lo, hi = paired_bootstrap_ci(values, base, resamples=resamples, seed=seed)
            out.append({"system": system, "baseline": best, "metric": metric, "diff": diff, "ci95": [lo, hi]})
    return out


def render_markdown(result: dict[str, Any]) -> str:
    """Tables for the report: overall means, per-category P@k, and the bootstrap comparisons."""
    metrics = result["metrics"]
    summary = result["summary"]
    lines = [
        f"Queries: {result['n_queries']}. Cut-offs from config: {', '.join(metrics)}.",
        "",
        "| System | " + " | ".join(metrics) + " |",
        "|---" * (len(metrics) + 1) + "|",
    ]
    lines += [
        f"| {system} | " + " | ".join(f"{summary[system]['mean'][m]:.3f}" for m in metrics) + " |" for system in SYSTEMS
    ]
    p_metric = metrics[0]
    categories = list(summary[SYSTEMS[0]]["by_category"])
    lines += ["", f"{p_metric} by category:", "", "| Category | n | " + " | ".join(SYSTEMS) + " |"]
    lines.append("|---" * (len(SYSTEMS) + 2) + "|")
    for cat in categories:
        n = summary[SYSTEMS[0]]["by_category"][cat]["n"]
        cells = " | ".join(f"{summary[s]['by_category'][cat][p_metric]:.3f}" for s in SYSTEMS)
        lines.append(f"| {cat} | {n} | {cells} |")
    lines += ["", "Paired bootstrap (95% CI of the mean difference over queries):", ""]
    for c in result["comparisons"]:
        lo, hi = c["ci95"]
        verdict = "CI excludes 0" if lo > 0 or hi < 0 else "CI includes 0"
        lines.append(
            f"- {c['system']} - {c['baseline']} on {c['metric']}: {c['diff']:+.3f} [{lo:+.3f}, {hi:+.3f}] ({verdict})"
        )
    return "\n".join(lines) + "\n"


def run_retrieval_eval(
    entries: Sequence[ResolvedEntry],
    retriever: EvalRetriever,
    reranker: CrossEncoderLike,
    to_english: ToEnglish,
    settings: Settings,
    corpus_hash: str,
) -> dict[str, Any]:
    """Every system on every query: per-query rows, summary, bootstrap comparisons and the config used."""
    cut = Cutoffs(settings.rerank_top, settings.top_n)
    rows = evaluate_queries(entries, lambda q: ranked_lists(retriever, reranker, q), to_english, cut)
    summary = summarize(rows, cut)
    resamples, seed = settings.eval_bootstrap_resamples, settings.eval_seed
    return {
        "n_queries": len(rows),
        "metrics": list(cut.names),
        "config": {
            "dense_k": settings.dense_k,
            "sparse_k": settings.sparse_k,
            "rrf_k": settings.rrf_k,
            "top_n": settings.top_n,
            "rerank_top": settings.rerank_top,
            "embedding_model": settings.embedding_model,
            "reranker_model": settings.reranker_model,
            "bootstrap_resamples": resamples,
            "seed": seed,
            "corpus_hash": corpus_hash,
        },
        "summary": summary,
        "comparisons": compare(rows, summary, cut, resamples=resamples, seed=seed),
        "per_query": rows,
    }


def main(
    argv: Sequence[str] | None = None,
    settings: Settings | None = None,
    retriever: EvalRetriever | None = None,
    reranker: CrossEncoderLike | None = None,
    to_english: ToEnglish | None = None,
) -> int:
    """CLI. 0 on success, 1 when the ground truth is invalid, 2 when chunks.json or the indexes are missing/stale."""
    parser = argparse.ArgumentParser(description="Evaluate FAISS, BM25, hybrid and hybrid+rerank on the ground truth.")
    parser.add_argument("--ground-truth", type=Path, help="default: eval/ground_truth.json")
    parser.add_argument("--out-dir", type=Path, help="default: eval/results")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    try:
        store = ChunkStore.load(settings.chunks_path)
        if retriever is None:
            use_offline_models()
            retriever = load_retriever(settings)
    except (IndexMismatchError, FileNotFoundError) as err:
        print(err, file=sys.stderr)
        return 2
    truth = load_ground_truth(args.ground_truth or settings.ground_truth_path, store, settings.acts)
    if not truth.ok:
        print(
            "ground truth invalid (see python eval/validate_ground_truth.py):",
            *truth.problems,
            sep="\n  ",
            file=sys.stderr,
        )
        return 1
    reranker = reranker or CEReranker(
        settings.reranker_model, settings.reranker_max_length, settings.reranker_batch_size
    )
    result = run_retrieval_eval(
        truth.entries, retriever, reranker, to_english or marian_to_english(settings), settings, store.corpus_hash
    )
    out_dir = args.out_dir or settings.eval_results_dir
    markdown = render_markdown(result)
    write_json(out_dir / "retrieval.json", result)
    (out_dir / "retrieval.md").write_text(markdown, encoding="utf-8")
    print(markdown, end="")
    print(f"saved {out_dir / 'retrieval.json'} and retrieval.md")
    return 0
