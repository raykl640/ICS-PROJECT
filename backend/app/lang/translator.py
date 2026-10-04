"""MarianMT (Helsinki-NLP opus-mt) behind the Translator protocol (ARCHITECTURE.md §8.2).

Best effort only: these models were trained on general and religious text, not legal text, so legal nuance can be
lost. Callers protect citations with lang.protect and show users the English original where translation fails.
"""

import threading
from typing import Any, Literal, Protocol

from backend.app.config import Settings, get_settings
from backend.app.lang.segment import segment
from backend.app.retrieval.embedder import hf_offline

Direction = Literal["sw-en", "en-sw"]

_WARMUP_TEXT: dict[Direction, str] = {"sw-en": "Habari ya asubuhi.", "en-sw": "Good morning."}


class _BatchModel(Protocol):
    """A loaded seq2seq model that translates a batch of short texts."""

    def generate(self, texts: list[str], num_beams: int, max_new_tokens: int) -> list[str]: ...


class _HFMarian:
    """transformers MarianMT tokenizer + model on CPU, decoded deterministically with beam search (no sampling)."""

    def __init__(self, model_name: str) -> None:
        from transformers import MarianMTModel, MarianTokenizer  # heavy imports, only when a real model is used

        self._tokenizer = MarianTokenizer.from_pretrained(model_name, local_files_only=hf_offline())
        # Any: transformers' generate() stubs reject MarianMTModel as self. from_pretrained returns eval mode.
        self._model: Any = MarianMTModel.from_pretrained(model_name, local_files_only=hf_offline())

    def generate(self, texts: list[str], num_beams: int, max_new_tokens: int) -> list[str]:
        """Translate one batch; inputs over the model's 512-token limit are truncated by the tokenizer."""
        import torch

        encoded = self._tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
        with torch.inference_mode():
            output = self._model.generate(
                **encoded, num_beams=num_beams, do_sample=False, max_new_tokens=max_new_tokens
            )
        decoded: list[str] = self._tokenizer.batch_decode(output, skip_special_tokens=True)
        return decoded


_MODELS: dict[str, _BatchModel] = {}
_MODELS_LOCK = threading.Lock()


def _build_model(model_name: str) -> _BatchModel:
    """Load a Marian model (cache-only when HF_HUB_OFFLINE is set)."""
    return _HFMarian(model_name)


def _shared_model(model_name: str) -> _BatchModel:
    """One loaded model per name per process, loaded on first use (never at import)."""
    with _MODELS_LOCK:
        if model_name not in _MODELS:
            _MODELS[model_name] = _build_model(model_name)
        return _MODELS[model_name]


class MarianTranslator:
    """One-direction translator: segments text by line and sentence, translates the pieces in batches."""

    def __init__(self, direction: Direction, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self.model_name = self._settings.translator_sw_en if direction == "sw-en" else self._settings.translator_en_sw

    def translate(self, text: str) -> str:
        """Translate text, keeping line breaks and list markers; blank input never loads the model."""
        s = self._settings
        parts = segment(text, s.translate_max_tokens, s.tokens_per_word)
        translated = iter(self.translate_batch([p.text for p in parts if p.translate]))
        return "".join(next(translated) if p.translate else p.text for p in parts)

    def translate_batch(self, texts: list[str]) -> list[str]:
        """Translate already-short texts, translate_batch_size at a time."""
        if not texts:
            return []
        s = self._settings
        model = _shared_model(self.model_name)
        out: list[str] = []
        for start in range(0, len(texts), s.translate_batch_size):
            batch = texts[start : start + s.translate_batch_size]
            out += model.generate(batch, s.translate_num_beams, s.translate_max_new_tokens)
        return out


def warmup(direction: Direction, settings: Settings | None = None) -> None:
    """Load a direction's model and translate one sentence so the first real request is not slowed."""
    MarianTranslator(direction, settings).translate(_WARMUP_TEXT[direction])
