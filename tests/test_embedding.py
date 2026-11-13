"""eq. (2) sentence embeddings: no weights are loaded in these tests."""

import pytest

from liskill.understand import embedding
from liskill.understand.dataset import dedupe_sentences
from liskill.understand.embedding import QwenEmbeddingEncoder, cosine


class StubModel:
    """Records the kwargs of ``SentenceTransformer.encode`` and returns unit vectors."""

    def __init__(self) -> None:
        self.calls = []
        self.vector = [1.0, 0.0]

    def encode(self, texts, **kwargs):
        self.calls.append({"texts": list(texts), **kwargs})
        return [list(self.vector) for _ in texts]


class FakeDenseEncoder:
    """Two-dimensional encoder: 'Permission' -> e1, everything else -> e2."""

    def __init__(self) -> None:
        self.batches = []

    def encode_documents(self, texts):
        self.batches.append(list(texts))
        return [[1.0, 0.0] if "Permission" in text else [0.0, 1.0] for text in texts]


def test_cosine_accepts_dense_and_sparse_vectors():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine({"a": 1.0}, {"a": 2.0, "b": 1.0}) == pytest.approx(2.0 / (1 * 5 ** 0.5))
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_documents_are_encoded_without_a_prompt_and_queries_with_one():
    encoder = QwenEmbeddingEncoder(batch_size=8)
    encoder._encoder = StubModel()  # bypasses the model download entirely

    encoder.encode_documents(["The capital of China is Beijing."])
    encoder.encode_queries(["What is the capital of China?"])

    document_call, query_call = encoder._encoder.calls
    assert document_call["prompt_name"] is None
    assert query_call["prompt_name"] == "query"
    assert document_call["batch_size"] == 8
    assert document_call["normalize_embeddings"] is True


def test_encoder_is_lazy_and_reports_a_missing_dependency(monkeypatch):
    encoder = QwenEmbeddingEncoder()
    assert encoder.available() in (True, False)  # probing must not import the stack

    monkeypatch.setattr(embedding, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="sentence-transformers is not installed"):
        encoder.encode_documents(["x"])


def test_dedupe_batches_once_and_keeps_one_per_cluster():
    encoder = FakeDenseEncoder()
    pairs = [
        ("MIT", "Permission is hereby granted, free of charge"),
        ("MIT", "Permission is hereby granted, free of charge, to any person"),
        ("GPL-3.0-only", "Everyone is permitted to copy and distribute"),
    ]
    kept = dedupe_sentences(pairs, threshold=0.95, encoder=encoder)

    assert len(encoder.batches) == 1, "sentences must be encoded in one batch"
    assert [license_id for license_id, _ in kept] == ["MIT", "GPL-3.0-only"]
