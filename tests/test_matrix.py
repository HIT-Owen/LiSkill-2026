"""Compatibility matrix (Table 8) and term database (§3.4.1)."""

import pytest

from liskill.conflict.matrix import (
    CONFLICT,
    DEPENDS,
    NO_CONFLICT,
    conditions_compatible,
    edge_conflicts,
    extract_conditions,
    judge_term,
    lookup,
)
from liskill.conflict.termdb import TermDatabase, missing_profile
from liskill.data_collection_preprocessing.licenses.reference import build_reference_set
from liskill.ontology import CONFLICT_TERMS


@pytest.fixture(scope="module")
def termdb() -> TermDatabase:
    return TermDatabase(build_reference_set()).build()


def test_matrix_matches_table_8():
    assert lookup("CAN", "CAN") == NO_CONFLICT
    assert lookup("CAN", "MUST") == CONFLICT
    assert lookup("CAN", "CANNOT") == CONFLICT
    assert lookup("MUST", "CAN") == NO_CONFLICT
    assert lookup("MUST", "MUST") == DEPENDS
    assert lookup("MUST", "CANNOT") == CONFLICT
    assert lookup("CANNOT", "CAN") == NO_CONFLICT
    assert lookup("CANNOT", "MUST") == CONFLICT
    assert lookup("CANNOT", "CANNOT") == NO_CONFLICT


def test_conditions_are_extracted_and_compared():
    conditions = extract_conditions(
        "You may convey the work, provided that you publish the copyright notice."
    )
    assert conditions
    assert conditions_compatible(conditions, set()) is True
    assert conditions_compatible(conditions, conditions) is True
    assert conditions_compatible({"must publish the notice"}, {"must not publish the notice"}) is False


def test_depends_is_resolved_by_conditions():
    # identical conditions -> compatible
    assert judge_term("T31", "MUST", "MUST", "provided that X", "provided that X") is None
    # mutually exclusive conditions -> conflict
    conflict = judge_term(
        "T31",
        "MUST",
        "MUST",
        "provided that you must publish the notice",
        "provided that you must not publish the notice",
    )
    assert conflict is not None
    assert conflict.relation == DEPENDS


def test_term_database_profiles_are_complete(termdb):
    profile = termdb.profile("MIT")
    assert len(profile) == 31
    assert set(profile) == {f"T{i}" for i in range(1, 32)}


def test_defaults_follow_table_7(termdb):
    mit = termdb.profile("MIT")
    # D1 — obligations default to CAN when never mentioned
    assert mit["T30"] == "CAN"
    # D2 — a catch-all grant carries the unmentioned rights
    assert termdb.grant("MIT") is True
    assert mit["T18"] == "CAN"


def test_missing_profile_assumes_no_grant():
    profile = missing_profile()
    assert profile["T1"] == "CANNOT"
    assert profile["T31"] == "CAN"


def test_permissive_pairs_do_not_conflict(termdb):
    pairs = [
        ("MIT", "MIT"),
        ("MIT", "Apache-2.0"),
        ("Apache-2.0", "BSD-3-Clause"),
        ("BSD-3-Clause", "ISC"),
    ]
    for parent, child in pairs:
        assert edge_conflicts(termdb.profile(parent), termdb.profile(child), terms=CONFLICT_TERMS) == []


def test_copyleft_child_conflicts_under_permissive_parent(termdb):
    conflicts = edge_conflicts(
        termdb.profile("MIT"), termdb.profile("GPL-3.0-only"), terms=CONFLICT_TERMS
    )
    terms = {c.term_id for c in conflicts}
    assert "T31" in terms and "T23" in terms


def test_copyleft_parent_accepts_permissive_child(termdb):
    assert (
        edge_conflicts(
            termdb.profile("GPL-3.0-only"), termdb.profile("MIT"), terms=CONFLICT_TERMS
        )
        == []
    )


def test_usage_restriction_conflicts_on_commercial_use(termdb):
    conflicts = edge_conflicts(
        termdb.profile("MIT"), termdb.profile("CC-BY-NC-4.0"), terms=CONFLICT_TERMS
    )
    assert "T5" in {c.term_id for c in conflicts}
