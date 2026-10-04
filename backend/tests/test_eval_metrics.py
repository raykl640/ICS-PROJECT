import math

import pytest

from backend.app.evaluation.metrics import (
    describe,
    fleiss_kappa,
    paired_bootstrap_ci,
    percent_agreement,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

RANKED = ["a", "b", "c", "d", "e", "f", "g"]


def test_precision_at_k_counts_relevant_in_the_first_k_over_k() -> None:
    assert precision_at_k(RANKED, {"b", "e", "g"}, 5) == pytest.approx(2 / 5)
    assert precision_at_k(RANKED, {"z"}, 5) == 0.0
    assert precision_at_k(["a", "b"], {"a", "b"}, 5) == pytest.approx(2 / 5)  # short lists still divide by k


def test_recall_at_k_is_share_of_relevant_found() -> None:
    assert recall_at_k(RANKED, {"b", "g", "z"}, 20) == pytest.approx(2 / 3)
    assert recall_at_k(RANKED, {"g"}, 5) == 0.0
    with pytest.raises(ValueError):
        recall_at_k(RANKED, set(), 5)


def test_reciprocal_rank_uses_first_relevant_hit() -> None:
    assert reciprocal_rank(RANKED, {"c", "f"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(RANKED, {"a"}) == 1.0
    assert reciprocal_rank(RANKED, {"z"}) == 0.0


def test_metric_k_must_be_positive() -> None:
    with pytest.raises(ValueError):
        precision_at_k(RANKED, {"a"}, 0)


def test_paired_bootstrap_ci_constant_shift_and_reproducibility() -> None:
    a = [0.4, 0.6, 0.8, 1.0]
    b = [0.2, 0.4, 0.6, 0.8]
    diff, lo, hi = paired_bootstrap_ci(a, b, resamples=500, seed=0)
    assert (diff, lo, hi) == pytest.approx((0.2, 0.2, 0.2))
    noisy = [0.0, 1.0, 0.0, 1.0, 1.0]
    zeros = [0.0] * 5
    first = paired_bootstrap_ci(noisy, zeros, resamples=1000, seed=7)
    assert first == paired_bootstrap_ci(noisy, zeros, resamples=1000, seed=7)
    assert first[0] == pytest.approx(0.6)
    assert first[1] <= first[0] <= first[2]
    with pytest.raises(ValueError):
        paired_bootstrap_ci([1.0], [1.0, 2.0], resamples=10, seed=0)


def test_fleiss_kappa_matches_the_published_worked_example() -> None:
    # Fleiss (1971) style worked example: 10 subjects, 14 raters, 5 categories; kappa = 0.210.
    counts = [
        [0, 0, 0, 0, 14],
        [0, 2, 6, 4, 2],
        [0, 0, 3, 5, 6],
        [0, 3, 9, 2, 0],
        [2, 2, 8, 1, 1],
        [7, 7, 0, 0, 0],
        [3, 2, 6, 3, 0],
        [2, 5, 3, 2, 2],
        [6, 5, 2, 1, 0],
        [0, 2, 2, 3, 7],
    ]
    kappa = fleiss_kappa(counts)
    assert kappa is not None
    assert kappa == pytest.approx(0.2099, abs=5e-4)


def test_fleiss_kappa_small_hand_computed_cases() -> None:
    # 3 raters, 2 categories. Items: unanimous yes, unanimous no, split 2/1, split 2/1.
    # P_i = 1, 1, 1/3, 1/3 -> P̄ = 2/3; p = (2+0+... ) column totals 3+0+2+1=6 yes, 6 no -> P_e = 0.5; kappa = 1/3.
    counts = [[3, 0], [0, 3], [2, 1], [1, 2]]
    kappa = fleiss_kappa(counts)
    assert kappa is not None
    assert kappa == pytest.approx(1 / 3)
    assert fleiss_kappa([[3, 0], [0, 3]]) == pytest.approx(1.0)
    assert fleiss_kappa([[3, 0], [3, 0]]) is None  # one category only: chance agreement is 1, kappa undefined
    with pytest.raises(ValueError):
        fleiss_kappa([[3, 0], [1, 1]])  # unequal raters per item


def test_percent_agreement_all_agree_and_mean_pairwise() -> None:
    counts = [[3, 0], [0, 3], [2, 1], [1, 2]]
    unanimous, pairwise = percent_agreement(counts)
    assert unanimous == pytest.approx(0.5)
    assert pairwise == pytest.approx(2 / 3)


def test_describe_summary_statistics() -> None:
    stats = describe([1.0, 2.0, 3.0, 4.0])
    assert stats == {
        "n": 4,
        "mean": pytest.approx(2.5),
        "sd": pytest.approx(math.sqrt(5 / 3)),
        "median": pytest.approx(2.5),
        "min": 1.0,
        "max": 4.0,
    }
    assert describe([5.0])["sd"] == 0.0
    assert describe([]) == {"n": 0}
