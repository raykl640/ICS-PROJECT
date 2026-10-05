"""Semantic scope check: is a question about the situations the corpus covers, however it is worded?

The cross-encoder scores lay wording ("cop slapped me") as low as unrelated text, so it cannot tell the two apart on its
own. This compares the question's embedding with example questions inside and outside the corpus's scope (scope.yaml)
and returns the margin: mean of the top-k in-scope similarities minus the mean of the top-k out-of-scope ones.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import yaml

from backend.app.config import Settings
from backend.app.interfaces import Embedder


@dataclass(frozen=True)
class ScopeExamples:
    """Example questions inside and outside the corpus's scope, groups flattened in file order."""

    in_scope: list[str]
    out_scope: list[str]


def _flatten(data: dict[str, object], key: str) -> list[str]:
    """All strings of one top-level key's groups; ValueError if missing, empty or malformed."""
    groups = data.get(key)
    if not isinstance(groups, dict) or not groups:
        raise ValueError(f"scope file: '{key}' must be a non-empty mapping of groups")
    texts: list[str] = []
    for name, items in groups.items():
        if not isinstance(items, list) or not items:
            raise ValueError(f"scope file: group '{key}.{name}' must be a non-empty list")
        if not all(isinstance(t, str) and t.strip() for t in items):
            raise ValueError(f"scope file: group '{key}.{name}' must contain only non-blank strings")
        texts.extend(items)
    return texts


def load_scope_examples(path: Path) -> ScopeExamples:
    """Read scope.yaml; ValueError if a list is missing or one example is in both lists."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("scope file: top level must be a mapping")
    examples = ScopeExamples(_flatten(data, "in_scope"), _flatten(data, "out_of_scope"))
    if set(examples.in_scope) & set(examples.out_scope):
        raise ValueError("scope file: an example appears in both in_scope and out_of_scope")
    return examples


def _top_mean(similarities: npt.NDArray[np.float32], k: int) -> float:
    """Mean of the k largest values (all of them if there are fewer)."""
    return float(np.sort(similarities)[-k:].mean())


class ScopeClassifier:
    """Embeds the examples once; margin() is one question embedding plus two small matrix products."""

    def __init__(self, embedder: Embedder, examples: ScopeExamples, neighbours: int) -> None:
        if neighbours <= 0:
            raise ValueError("neighbours must be positive")
        self.neighbours = neighbours
        self._embedder = embedder
        self._in = embedder.encode(examples.in_scope)
        self._out = embedder.encode(examples.out_scope)

    def margin(self, question: str) -> float:
        """Top-k mean cosine to in-scope examples minus top-k mean to out-of-scope ones (vectors are normalised)."""
        vector = self._embedder.encode([question])[0]
        return _top_mean(self._in @ vector, self.neighbours) - _top_mean(self._out @ vector, self.neighbours)


def load_scope(settings: Settings, embedder: Embedder) -> ScopeClassifier:
    """ScopeClassifier over settings.scope_path with settings.scope_neighbours."""
    return ScopeClassifier(embedder, load_scope_examples(settings.scope_path), settings.scope_neighbours)
