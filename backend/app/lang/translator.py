"""Translation interface. The MarianMT implementation is added in M6."""

from typing import Protocol


class Translator(Protocol):
    def translate(self, text: str) -> str: ...


class FakeTranslator:
    """Prefixes text with a direction tag so tests can see a translation happened."""

    def __init__(self, tag: str) -> None:
        self.tag = tag

    def translate(self, text: str) -> str:
        return f"[{self.tag}] {text}"
