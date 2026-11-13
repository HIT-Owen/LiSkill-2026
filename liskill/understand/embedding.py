"""Sentence encoder for eq. (2) — Qwen3-Embedding-0.6B.

§3.3.2 removes near-duplicate licence sentences by cosine similarity of sentence
embeddings, encoded with ``Qwen/Qwen3-Embedding-0.6B``.  De-duplication compares
sentences with each other, so both sides are encoded as *documents* (no prompt);
the ``query`` prompt is exposed for retrieval-style callers.

The dependency is imported on first use only, so ``import liskill`` stays
stdlib-only and the offline demo never needs the weights::

    pip install 'liskill[embed]'

    encoder = QwenEmbeddingEncoder()
    vectors = encoder.encode_documents(sentences)   # documents: no prompt
    encoder.similarity(vectors[0], vectors[1])      # cosine
"""

from __future__ import annotations

import importlib.util
import math
from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Sequence

#: the embedding model of §3.3.2
MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"


def cosine(left: Any, right: Any) -> float:
    """Cosine similarity of two vectors.

    Accepts both a dense embedding (list / tuple / array) and the sparse count
    vector of the offline stand-in, so the caller never has to care which
    encoder produced it.
    """
    if isinstance(left, Mapping):
        shared = set(left) & set(right)
        numerator = sum(left[key] * right[key] for key in shared)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
    else:
        left_values = [float(value) for value in left]
        right_values = [float(value) for value in right]
        numerator = sum(a * b for a, b in zip(left_values, right_values))
        left_norm = math.sqrt(sum(value * value for value in left_values))
        right_norm = math.sqrt(sum(value * value for value in right_values))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def is_available() -> bool:
    """True when ``sentence-transformers`` can be imported (no model download)."""
    return importlib.util.find_spec("sentence_transformers") is not None


class QwenEmbeddingEncoder:
    """Lazily loaded ``Qwen3-Embedding-0.6B`` wrapper.

    Nothing touches the network or the cache until the first ``encode_*`` call,
    which is what keeps the tests and the demo weight-free.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        batch_size: int = 64,
        device: Optional[str] = None,
        attn_implementation: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device
        #: pass ``"flash_attention_2"`` for the accelerated path of the model card
        self.attn_implementation = attn_implementation
        self._encoder = None

    # ------------------------------------------------------------------ loading
    def available(self) -> bool:
        return is_available()

    def _load(self):
        if self._encoder is not None:
            return self._encoder
        if not is_available():
            raise RuntimeError(
                "sentence-transformers is not installed; run "
                "pip install 'liskill[embed]' or pass embedder=None to stay offline"
            )
        from sentence_transformers import SentenceTransformer

        kwargs: Dict[str, Any] = {}
        if self.device:
            kwargs["device"] = self.device
        if self.attn_implementation:
            kwargs["model_kwargs"] = {
                "attn_implementation": self.attn_implementation,
                "device_map": "auto",
            }
            kwargs["tokenizer_kwargs"] = {"padding_side": "left"}
        self._encoder = SentenceTransformer(self.model_name, **kwargs)
        return self._encoder

    # ---------------------------------------------------------------- encoding
    def _encode(self, texts: Sequence[str], prompt_name: Optional[str]) -> List[List[float]]:
        model = self._load()
        vectors = model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
            prompt_name=prompt_name,
        )
        return [[float(value) for value in vector] for vector in vectors]

    def encode_documents(self, texts: Sequence[str]) -> List[List[float]]:
        """Encode sentences as documents — the path eq. (2) de-duplication uses."""
        return self._encode(texts, prompt_name=None)

    def encode_queries(self, texts: Sequence[str]) -> List[List[float]]:
        """Encode retrieval queries with the model's ``query`` prompt."""
        return self._encode(texts, prompt_name="query")

    def similarity(self, left: Any, right: Any) -> float:
        """Cosine similarity, computed locally so both sides stay plain lists."""
        return cosine(left, right)
