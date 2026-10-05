from pathlib import Path

import pytest
import yaml

from backend.app.config import Settings
from backend.app.retrieval.scope import ScopeClassifier, ScopeExamples, load_scope, load_scope_examples
from backend.tests.fakes import FakeEmbedder

EXAMPLES = ScopeExamples(
    in_scope=["employer fired me without notice", "landlord locked my house", "police arrested me"],
    out_scope=["recipe for chapati", "football match score", "weather tomorrow"],
)


def _write(path: Path, data: object) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


@pytest.fixture
def clf() -> ScopeClassifier:
    return ScopeClassifier(FakeEmbedder(), EXAMPLES, neighbours=1)


def test_question_near_in_scope_examples_has_positive_margin(clf: ScopeClassifier) -> None:
    assert clf.margin("my employer fired me") > 0


def test_question_near_out_of_scope_examples_has_negative_margin(clf: ScopeClassifier) -> None:
    assert clf.margin("chapati recipe please") < 0


def test_question_near_neither_has_zero_margin(clf: ScopeClassifier) -> None:
    assert clf.margin("qxzv blorp") == 0.0


def test_neighbours_larger_than_example_count_uses_all_examples() -> None:
    wide = ScopeClassifier(FakeEmbedder(), EXAMPLES, neighbours=50)
    assert wide.margin("my employer fired me") > 0


def test_neighbours_must_be_positive() -> None:
    with pytest.raises(ValueError, match="neighbours"):
        ScopeClassifier(FakeEmbedder(), EXAMPLES, neighbours=0)


def test_load_flattens_groups(tmp_path: Path) -> None:
    path = _write(tmp_path / "s.yaml", {"in_scope": {"a": ["x", "y"], "b": ["z"]}, "out_of_scope": {"c": ["w"]}})
    assert load_scope_examples(path) == ScopeExamples(in_scope=["x", "y", "z"], out_scope=["w"])


@pytest.mark.parametrize(
    "data",
    [
        {"in_scope": {"a": ["x"]}},
        {"in_scope": {}, "out_of_scope": {"c": ["w"]}},
        {"in_scope": {"a": []}, "out_of_scope": {"c": ["w"]}},
        {"in_scope": {"a": ["x", 3]}, "out_of_scope": {"c": ["w"]}},
        {"in_scope": {"a": ["x", " "]}, "out_of_scope": {"c": ["w"]}},
        {"in_scope": ["x"], "out_of_scope": {"c": ["w"]}},
        {"in_scope": {"a": ["x"]}, "out_of_scope": {"c": ["x"]}},
    ],
)
def test_load_rejects_malformed_files(tmp_path: Path, data: object) -> None:
    with pytest.raises(ValueError, match="scope"):
        load_scope_examples(_write(tmp_path / "s.yaml", data))


def test_shipped_examples_load_and_are_distinct() -> None:
    examples = load_scope_examples(Settings().scope_path)
    assert len(examples.in_scope) >= 50 and len(examples.out_scope) >= 50
    assert len(set(examples.in_scope)) == len(examples.in_scope)
    assert len(set(examples.out_scope)) == len(examples.out_scope)


def test_load_scope_uses_settings() -> None:
    clf = load_scope(Settings(scope_neighbours=2), FakeEmbedder())
    assert clf.neighbours == 2


@pytest.fixture(scope="module")
def real_clf() -> ScopeClassifier:
    from backend.app.retrieval.embedder import STEmbedder

    settings = Settings()
    return load_scope(settings, STEmbedder(settings.embedding_model, settings.embed_batch_size))


@pytest.mark.real
@pytest.mark.parametrize(
    ("question", "in_scope"),
    [
        ("my boss hasnt paid my salary for 2 months", True),
        ("landlord took my stuff coz i owe rent", True),
        ("cop slapped me", True),
        ("someone grabbed my land", True),
        ("what is a good recipe for chapati and beef stew?", False),
        ("who won the football world cup in 2014?", False),
        ("hello", False),
    ],
)
def test_real_minilm_separates_lay_legal_questions_from_unrelated_ones(
    real_clf: ScopeClassifier, question: str, in_scope: bool
) -> None:
    assert (real_clf.margin(question) >= Settings().scope_margin) is in_scope
