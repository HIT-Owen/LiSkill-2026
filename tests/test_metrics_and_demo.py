"""Metrics (§4.1.3) and the end-to-end demo pipeline."""

import pytest

from liskill.demo.corpus import build_synthetic_ecosystem
from liskill.demo.run import run_demo
from liskill.eval.metrics import (
    detection_scores,
    license_understanding_scores,
    term_identification_scores,
)
from liskill.data_collection_preprocessing.licenses.reference import build_reference_set
from liskill.schema import TermAttitude


def ta(term_id: str, attitude: str) -> TermAttitude:
    return TermAttitude(term_id=term_id, attitude=attitude)


def test_term_identification_ignores_attitude():
    gold = [[ta("T5", "CANNOT"), ta("T3", "MUST")]]
    predicted = [[ta("T5", "CAN"), ta("T3", "MUST")]]
    score = term_identification_scores(predicted, gold)
    assert score.precision == 1.0 and score.recall == 1.0


def test_license_understanding_requires_the_attitude():
    gold = [[ta("T5", "CANNOT"), ta("T3", "MUST")]]
    predicted = [[ta("T5", "CAN"), ta("T3", "MUST")]]
    score = license_understanding_scores(predicted, gold)
    assert score.correct == 1
    assert score.precision == 0.5 and score.recall == 0.5
    assert score.f1 == pytest.approx(0.5)


def test_repeated_terms_are_matched_one_by_one():
    gold = [[ta("T2", "CAN"), ta("T2", "CAN")]]
    predicted = [[ta("T2", "CAN")]]
    score = term_identification_scores(predicted, gold)
    assert score.correct == 1 and score.recall == 0.5


def test_detection_scores():
    reported = [True, True, False, False]
    actual = [True, False, True, False]
    score = detection_scores(reported, actual)
    assert score.reported == 2
    assert score.fpr == 0.5   # 1 FP of 2 negatives
    assert score.fnr == 0.5   # 1 FN of 2 positives


def test_reference_set_merges_four_sources():
    reference = build_reference_set()
    entry = reference.get("Apache-2.0")
    assert entry is not None
    assert len(entry.sources) == 4
    assert entry.text_sha256
    assert reference.candidates
    assert reference.match_exact("apache 2.0") == "Apache-2.0"


def test_custom_license_registration_is_deterministic():
    reference = build_reference_set()
    first = reference.register_custom("Internal use only - ACME assets")
    second = reference.register_custom("Internal use only - ACME assets")
    assert first.license_id == second.license_id
    assert first.license_id.startswith("LIC-")


def test_synthetic_corpus_follows_the_reported_distribution():
    ecosystem = build_synthetic_ecosystem(size=300, seed=11, write_packages=False)
    assert len(ecosystem) == 300
    declared = sum(1 for value in ecosystem.ground_truth.values() if value[0] or value[1])
    assert 0 < declared < 300


def test_demo_runs_end_to_end(tmp_path):
    outcome = run_demo(
        size=40,
        workflows=12,
        seed=3,
        out_dir=tmp_path,
        understanding_sample=60,
        quiet=True,
    )
    assert outcome.report_path.exists()
    assert "DEMO DATA" in outcome.report
    assert outcome.summary["skills"] >= 40
    for section in ("§3.1", "RQ1", "RQ3"):
        assert section in outcome.report
