"""Metrics of §4.1.3.

License understanding is scored on ``(term, attitude)`` pairs with two levels:

* **term identification** — the term name matches, the attitude is ignored;
* **license understanding** — term name *and* attitude must match.

Both use the same precision / recall / F1 definitions (eq. (13)–(15));

    P = |correct| / |predicted|
    R = |correct| / |gold|
    F1 = 2PR / (P + R)

Detections reuse the paper's reporting units: ``#Report``, FPR (share of the
non-conflicting units that were reported) and FNR (share of the conflicting
units that were not reported).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ..schema import TermAttitude


@dataclass(frozen=True)
class PRF1:
    precision: float
    recall: float
    f1: float
    predicted: int
    gold: int
    correct: int

    def as_percent(self) -> Dict[str, float]:
        return {
            "P(%)": round(self.precision * 100, 2),
            "R(%)": round(self.recall * 100, 2),
            "F1(%)": round(self.f1 * 100, 2),
        }

    def __str__(self) -> str:
        return (
            f"P={self.precision:.4f} R={self.recall:.4f} F1={self.f1:.4f} "
            f"(pred={self.predicted}, gold={self.gold}, correct={self.correct})"
        )


@dataclass(frozen=True)
class DetectionScore:
    reported: int
    fpr: float
    fnr: float
    positives: int
    negatives: int

    def as_percent(self) -> Dict[str, float]:
        return {"#Report": self.reported, "FPR(%)": round(self.fpr * 100, 2), "FNR(%)": round(self.fnr * 100, 2)}


def _divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def multiset_prf1(predicted: Counter, gold: Counter) -> PRF1:
    """P/R/F1 over multisets (repeated terms are matched one by one)."""
    correct = sum((predicted & gold).values())
    predicted_total = sum(predicted.values())
    gold_total = sum(gold.values())
    precision = _divide(correct, predicted_total)
    recall = _divide(correct, gold_total)
    f1 = _divide(2 * precision * recall, precision + recall)
    return PRF1(precision, recall, f1, predicted_total, gold_total, correct)


def _term_counter(items: Iterable[TermAttitude]) -> Counter:
    return Counter(item.term_id for item in items)


def _pair_counter(items: Iterable[TermAttitude]) -> Counter:
    return Counter((item.term_id, item.attitude) for item in items)


def term_identification_scores(
    predicted: Sequence[Sequence[TermAttitude]], gold: Sequence[Sequence[TermAttitude]]
) -> PRF1:
    """Level 1 — term names only."""
    pred, ref = Counter(), Counter()
    for items in predicted:
        pred.update(_term_counter(items))
    for items in gold:
        ref.update(_term_counter(items))
    return multiset_prf1(pred, ref)


def license_understanding_scores(
    predicted: Sequence[Sequence[TermAttitude]], gold: Sequence[Sequence[TermAttitude]]
) -> PRF1:
    """Level 2 — ``(term, attitude)`` pairs."""
    pred, ref = Counter(), Counter()
    for items in predicted:
        pred.update(_pair_counter(items))
    for items in gold:
        ref.update(_pair_counter(items))
    return multiset_prf1(pred, ref)


def detection_scores(
    reported: Sequence[bool], actual: Sequence[bool]
) -> DetectionScore:
    """#Report / FPR / FNR over labelled units (issues, skills, edges, chains)."""
    positives = sum(1 for flag in actual if flag)
    negatives = len(actual) - positives
    true_positive = sum(1 for rep, act in zip(reported, actual) if rep and act)
    false_positive = sum(1 for rep, act in zip(reported, actual) if rep and not act)
    false_negative = sum(1 for rep, act in zip(reported, actual) if not rep and act)
    return DetectionScore(
        reported=sum(1 for flag in reported if flag),
        fpr=_divide(false_positive, negatives),
        fnr=_divide(false_negative, positives),
        positives=positives,
        negatives=negatives,
    )


def match_conflict_units(
    predicted: Set[Tuple[str, str, str]],
    gold: Set[Tuple[str, str, str]],
) -> Tuple[bool, bool]:
    """Return ``(reported, actual)`` for one unit given its conflict tuples."""
    return bool(predicted), bool(gold)
