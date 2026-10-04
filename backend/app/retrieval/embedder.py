"""sentence-transformers bi-encoder behind the Embedder protocol (all-MiniLM-L6-v2 in production)."""

import os

import numpy as np
import numpy.typing as npt

_TRUTHY = {"1", "true", "yes", "on"}


def hf_offline() -> bool:
    """True when HF_HUB_OFFLINE asks for cached model files only."""
    return os.environ.get("HF_HUB_OFFLINE", "").strip().lower() in _TRUTHY


class STEmbedder:
    """CPU SentenceTransformer producing L2-normalised float32 vectors; model loads from cache when offline."""

    def __init__(self, model_name: str, batch_size: int) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import (torch), only when a real model is used

        self._model = SentenceTransformer(model_name, device="cpu", local_files_only=hf_offline())
        dim = self._model.get_embedding_dimension()
        if dim is None:
            raise ValueError(f"{model_name} does not report an embedding dimension")
        self.dim: int = dim
        self._batch_size = batch_size

    def encode(self, texts: list[str]) -> npt.NDArray[np.float32]:
        """Batch-encode texts to unit-length vectors of shape (len(texts), dim)."""
        vectors = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    def count_tokens(self, text: str) -> int:
        """Word-piece count including [CLS]/[SEP], without truncation."""
        return len(self._model.tokenizer(text, add_special_tokens=True, truncation=False, verbose=False)["input_ids"])
