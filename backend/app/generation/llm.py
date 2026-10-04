"""LLM client interface. The Ollama streaming implementation is added in M5."""

from collections.abc import Iterator
from typing import Protocol


class LLMClient(Protocol):
    def stream(self, prompt: str) -> Iterator[str]:
        """Yield generated tokens in order."""
        ...

    def health(self) -> bool:
        """True if the backing model is reachable and loaded."""
        ...


class FakeLLM:
    """Yields scripted tokens and records every prompt it receives."""

    def __init__(self, tokens: list[str], healthy: bool = True) -> None:
        self.tokens = tokens
        self.healthy = healthy
        self.prompts: list[str] = []

    def stream(self, prompt: str) -> Iterator[str]:
        self.prompts.append(prompt)
        yield from self.tokens

    def health(self) -> bool:
        return self.healthy
