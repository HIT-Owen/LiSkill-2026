"""License understanding dataset construction (§3.3.2).

    full license texts  --NLTK-->  167,812 candidate sentences
                        --dedupe--> 82,940 sentences
                        --sample--> 28,578 annotated sentences
                        --split--> 20,005 / 2,858 / 5,715 (7:1:2)

Sentence de-duplication uses the cosine similarity of sentence embeddings
(eq. (2)), encoded with ``Qwen/Qwen3-Embedding-0.6B``
(:class:`~liskill.understand.embedding.QwenEmbeddingEncoder`).  To keep the
released package dependency-free the default encoder is a character n-gram
stand-in that behaves the same way for near-duplicate detection; pass
``encoder=QwenEmbeddingEncoder()`` for the paper's encoder.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..schema import TermAttitude
from ..understand.prompt import build_training_pair
from .embedding import cosine
from .reader import split_sentences

DEFAULT_SIMILARITY_THRESHOLD = 0.95
SPLIT_RATIOS = (0.7, 0.1, 0.2)


@dataclass
class SentenceSample:
    sentence: str
    license_id: str
    terms: List[TermAttitude] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "sentence": self.sentence,
            "license_id": self.license_id,
            "terms": [t.to_dict() for t in self.terms],
        }


# --------------------------------------------------------------------------- #
# sentence splitting and de-duplication
# --------------------------------------------------------------------------- #
def candidate_sentences(texts: Dict[str, str]) -> List[Tuple[str, str]]:
    """``[(license_id, sentence)]`` for every sentence of every license."""
    out: List[Tuple[str, str]] = []
    for license_id, text in texts.items():
        for sentence in split_sentences(text):
            if len(sentence) < 20:
                continue
            out.append((license_id, sentence))
    return out


def _char_ngrams(text: str, n: int = 3) -> Counter:
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    return Counter(normalized[i : i + n] for i in range(max(1, len(normalized) - n + 1)))


class NgramEmbedder:
    """Dependency-free stand-in for the sentence embedder of eq. (2)."""

    def __init__(self, n: int = 3) -> None:
        self.n = n

    def __call__(self, text: str) -> Counter:
        return _char_ngrams(text, self.n)

    def encode_documents(self, texts: Sequence[str]) -> List[Counter]:
        return [self(text) for text in texts]

    def similar(self, left: str, right: str) -> float:
        return cosine(self(left), self(right))


def dedupe_sentences(
    pairs: Sequence[Tuple[str, str]],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    encoder: Optional[object] = None,
) -> List[Tuple[str, str]]:
    """Keep one representative per near-duplicate cluster (eq. (2)).

    ``encoder`` is either the sentence encoder of
    :mod:`liskill.understand.embedding` (anything exposing
    ``encode_documents(texts)``, encoded in one batch) or a plain callable
    ``text -> vector``.
    """
    encoder = encoder if encoder is not None else NgramEmbedder()
    sentences = [sentence for _, sentence in pairs]
    batch_encode = getattr(encoder, "encode_documents", None)
    vectors = batch_encode(sentences) if batch_encode is not None else [encoder(s) for s in sentences]

    kept: List[Tuple[str, str]] = []
    kept_vectors: List[object] = []
    for (license_id, sentence), vector in zip(pairs, vectors):
        if any(cosine(vector, other) >= threshold for other in kept_vectors):
            continue
        kept.append((license_id, sentence))
        kept_vectors.append(vector)
    return kept


def split_samples(
    samples: Sequence[SentenceSample], seed: int = 20260501
) -> Dict[str, List[SentenceSample]]:
    """7:1:2 train / dev / test split (§4.1.1)."""
    ordered = sorted(samples, key=lambda s: hashlib.sha256(s.sentence.encode()).hexdigest())
    rng = random.Random(seed)
    rng.shuffle(ordered)
    total = len(ordered)
    train_end = int(total * SPLIT_RATIOS[0])
    dev_end = train_end + int(total * SPLIT_RATIOS[1])
    return {
        "train": list(ordered[:train_end]),
        "dev": list(ordered[train_end:dev_end]),
        "test": list(ordered[dev_end:]),
    }


# --------------------------------------------------------------------------- #
# annotation and export
# --------------------------------------------------------------------------- #
def pre_annotate(
    sentences: Sequence[Tuple[str, str]], reader, limit: Optional[int] = None
) -> List[SentenceSample]:
    """Stage 1 of §3.3.2 — LLM pre-annotation of (term, attitude) pairs.

    In the paper this calls DeepSeek-V4-Flash-0731; here any object exposing
    ``read_sentence`` works, including the offline reader.
    """
    samples: List[SentenceSample] = []
    for license_id, sentence in sentences[: limit or len(sentences)]:
        terms = reader.read_sentence(sentence)
        samples.append(SentenceSample(sentence=sentence, license_id=license_id, terms=terms))
    return samples


def export_jsonl(samples: Sequence[SentenceSample], path: str | Path) -> Path:
    """Write supervised pairs (Appendix-B prompt -> JSON target)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for sample in samples:
            payload = build_training_pair(
                sample.sentence, [t.to_dict() for t in sample.terms]
            )
            payload["license_id"] = sample.license_id
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def build_dataset(
    license_texts: Dict[str, str],
    reader,
    sample_size: int = 3000,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    seed: int = 20260501,
    out_dir: Optional[str | Path] = None,
    encoder: Optional[object] = None,
) -> Dict[str, object]:
    """Run the whole construction pipeline and optionally write JSONL splits.

    ``encoder`` defaults to the offline n-gram stand-in; pass
    ``QwenEmbeddingEncoder()`` to de-duplicate with the paper's encoder.
    """
    candidates = candidate_sentences(license_texts)
    deduped = dedupe_sentences(candidates, threshold=threshold, encoder=encoder)
    rng = random.Random(seed)
    rng.shuffle(deduped)
    sampled = deduped[:sample_size]
    annotated = pre_annotate(sampled, reader)
    splits = split_samples(annotated, seed=seed)

    if out_dir is not None:
        out = Path(out_dir)
        for name, items in splits.items():
            export_jsonl(items, out / f"{name}.jsonl")

    return {
        "candidate_sentences": len(candidates),
        "deduped_sentences": len(deduped),
        "annotated": len(annotated),
        "splits": {name: len(items) for name, items in splits.items()},
        "samples": splits,
    }
