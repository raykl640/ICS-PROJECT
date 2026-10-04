"""Embedding text for a chunk: header-prefixed, split into overlapping word windows when long."""

from dataclasses import dataclass

from backend.app.config import Settings
from backend.app.models import LegalChunk


@dataclass(frozen=True)
class WindowSpec:
    """Chunks longer than split_over words become windows of `words` words starting every `stride` words."""

    split_over: int
    words: int
    stride: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "WindowSpec":
        """Window sizes from config."""
        return cls(settings.embed_split_over_words, settings.embed_window_words, settings.embed_window_stride)


def chunk_header(chunk: LegalChunk) -> str:
    """'{act} — {unit} {num}: {title}. '; a schedule's section_num already names the unit."""
    unit = "" if chunk.unit_type == "schedule" else f"{chunk.unit_type.capitalize()} "
    return f"{chunk.act} — {unit}{chunk.section_num}: {chunk.section_title}. "


def make_windows(chunk: LegalChunk, spec: WindowSpec) -> list[str]:
    """Embedding texts for one chunk, each prefixed with its header; the last window always reaches the end."""
    words = chunk.text.split()
    header = chunk_header(chunk)
    if len(words) <= spec.split_over:
        return [header + " ".join(words)]
    windows = []
    start = 0
    while True:
        windows.append(header + " ".join(words[start : start + spec.words]))
        if start + spec.words >= len(words):
            return windows
        start += spec.stride
