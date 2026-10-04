"""Evaluation statistics: ranking metrics, paired bootstrap, inter-rater agreement and descriptive summaries."""

import statistics
from collections.abc import Sequence, Set

import numpy as np


def _check_k(k: int) -> None:
    """Cut-offs must be positive."""
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")


def precision_at_k(ranked: Sequence[str], relevant: Set[str], k: int) -> float:
    """Relevant ids among the first k, divided by k (a list shorter than k still divides by k)."""
    _check_k(k)
    return sum(chunk_id in relevant for chunk_id in ranked[:k]) / k


def recall_at_k(ranked: Sequence[str], relevant: Set[str], k: int) -> float:
    """Share of the relevant ids that appear in the first k."""
    _check_k(k)
    if not relevant:
        raise ValueError("recall needs at least one relevant id")
    return len(relevant & set(ranked[:k])) / len(relevant)


def reciprocal_rank(ranked: Sequence[str], relevant: Set[str]) -> float:
    """1 / rank of the first relevant id (1-indexed), 0 when none is ranked."""
    return next((1 / rank for rank, chunk_id in enumerate(ranked, start=1) if chunk_id in relevant), 0.0)


def paired_bootstrap_ci(
    a: Sequence[float], b: Sequence[float], *, resamples: int, seed: int, alpha: float = 0.05
) -> tuple[float, float, float]:
    """(mean(a - b), lower, upper): percentile CI of the mean paired difference, resampling queries with replacement."""
    if len(a) != len(b) or not a:
        raise ValueError("paired samples must be non-empty and of equal length")
    diffs = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    picks = np.random.default_rng(seed).integers(0, len(diffs), size=(resamples, len(diffs)))
    means = diffs[picks].mean(axis=1)
    lower, upper = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(diffs.mean()), float(lower), float(upper)


def _raters_per_item(counts: Sequence[Sequence[int]]) -> int:
    """The common number of ratings per item; ValueError if items differ or fewer than two raters."""
    totals = {sum(row) for row in counts}
    if len(totals) != 1 or min(totals) < 2:
        raise ValueError(f"every item needs the same number (>= 2) of ratings, got {sorted(totals)}")
    return totals.pop()


def _item_agreement(row: Sequence[int], raters: int) -> float:
    """Share of rater pairs that agree on one item."""
    return sum(c * (c - 1) for c in row) / (raters * (raters - 1))


def fleiss_kappa(counts: Sequence[Sequence[int]]) -> float | None:
    """Fleiss' kappa from an items x categories count matrix; None when chance agreement is 1 (one category used)."""
    raters = _raters_per_item(counts)
    observed = sum(_item_agreement(row, raters) for row in counts) / len(counts)
    shares: list[float] = [sum(column) / (len(counts) * raters) for column in zip(*counts, strict=True)]
    chance = sum(p * p for p in shares)
    if chance >= 1.0:
        return None
    return (observed - chance) / (1 - chance)


def percent_agreement(counts: Sequence[Sequence[int]]) -> tuple[float, float]:
    """(share of items where all raters agree, mean pairwise agreement P̄ as used by Fleiss' kappa)."""
    raters = _raters_per_item(counts)
    unanimous = sum(max(row) == raters for row in counts) / len(counts)
    pairwise = sum(_item_agreement(row, raters) for row in counts) / len(counts)
    return unanimous, pairwise


def describe(values: Sequence[float]) -> dict[str, float]:
    """n, mean, sample sd, median, min and max ({"n": 0} for no data)."""
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "sd": statistics.stdev(values) if len(values) > 1 else 0.0,
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }
