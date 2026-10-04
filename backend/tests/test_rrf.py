import pytest

from backend.app.config import Settings
from backend.app.retrieval.rrf import Fused, rrf


def test_scores_match_hand_computed_values_for_two_overlapping_lists() -> None:
    dense = ["a", "b", "c"]
    sparse = ["c", "a", "d"]
    fused = rrf(dense, sparse, k=60)
    # a: 1/61 + 1/62; c: 1/63 + 1/61; b: 1/62; d: 1/63
    assert [f.chunk_id for f in fused] == ["a", "c", "b", "d"]
    assert [f.score for f in fused] == pytest.approx([0.0325224748, 0.0322664585, 0.0161290323, 0.0158730159])
    assert [f.ranks for f in fused] == [(1, 2), (3, 1), (2, None), (None, 3)]


def test_chunk_in_both_lists_beats_a_single_list_top_hit() -> None:
    fused = rrf(["x", "both"], ["y", "both"], k=60)
    assert fused[0].chunk_id == "both"
    assert fused[0].score == pytest.approx(2 / 62)


def test_ties_break_on_best_rank_then_chunk_id() -> None:
    fused = rrf(["b", "a", "e"], ["c", "d", "f"], k=60)
    assert [f.chunk_id for f in fused] == ["b", "c", "a", "d", "e", "f"]
    swapped = rrf(["c", "a", "e"], ["b", "d", "f"], k=60)
    mirrored = rrf(["b", "d", "f"], ["c", "a", "e"], k=60)
    assert [f.chunk_id for f in swapped] == [f.chunk_id for f in mirrored] == ["b", "c", "a", "d", "e", "f"]
    assert swapped[0] == Fused("b", pytest.approx(1 / 61), (None, 1))  # type: ignore[arg-type]


def test_k_controls_the_smoothing() -> None:
    assert rrf(["a"], k=0)[0].score == pytest.approx(1.0)
    assert rrf(["a"], k=60)[0].score == pytest.approx(1 / 61)
    assert Settings().rrf_k == 60


def test_duplicates_within_a_list_count_once_at_their_best_rank() -> None:
    assert rrf(["a", "b", "a"], k=60) == [Fused("a", 1 / 61, (1,)), Fused("b", 1 / 62, (2,))]


def test_empty_and_single_lists() -> None:
    assert rrf([], [], k=60) == []
    assert [f.ranks for f in rrf(["a", "b"], [], k=60)] == [(1, None), (2, None)]
