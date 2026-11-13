"""Ontology and sentence-level reader (§3.3)."""

from liskill.data_collection_preprocessing.licenses.legal_texts import LICENSE_TEXTS
from liskill.ontology import ATTITUDES, CONFLICT_TERMS, TERMS, strictest
from liskill.understand.reader import HeuristicLicenseReader, split_clauses, split_sentences


def profile(license_id: str) -> dict:
    reader = HeuristicLicenseReader()
    return {ta.term_id: ta.attitude for ta in reader.read_text(LICENSE_TEXTS[license_id].text)}


def test_ontology_has_31_terms_and_three_attitudes():
    assert len(TERMS) == 31
    assert [t.tid for t in TERMS] == [f"T{i}" for i in range(1, 32)]
    assert ATTITUDES == ("CAN", "CANNOT", "MUST")


def test_conflict_terms_are_a_subset_of_the_ontology():
    ids = {t.tid for t in TERMS}
    assert set(CONFLICT_TERMS) <= ids
    # formalities stack instead of conflicting
    assert "T20" not in CONFLICT_TERMS
    assert "T31" in CONFLICT_TERMS


def test_strictest_operator_follows_table_7():
    assert strictest(["CAN", "MUST"]) == "MUST"
    assert strictest(["CAN", "MUST", "CANNOT"]) == "CANNOT"
    assert strictest(["CAN"]) == "CAN"


def test_splitter_keeps_sentences_and_clauses():
    sentences = split_sentences("You may copy. You may not sell; unless permitted.")
    assert sentences[0] == "You may copy."
    assert len(split_clauses("You may copy; you may not sell")) == 2


def test_mit_profile():
    prof = profile("MIT")
    assert prof["T1"] == "CAN" and prof["T2"] == "CAN" and prof["T5"] == "CAN"
    assert prof["T20"] == "MUST" and prof["T21"] == "MUST"
    # MIT never imposes copyleft: the term is simply not observed
    assert prof.get("T31", "CAN") == "CAN"


def test_gpl3_profile_has_strong_copyleft():
    prof = profile("GPL-3.0-only")
    assert prof["T31"] == "MUST"      # keep the same license
    assert prof["T23"] == "MUST"      # offer the source
    assert prof["T9"] == "CANNOT"     # sublicensing is not allowed


def test_non_commercial_license_refuses_commercial_use():
    assert profile("CC-BY-NC-4.0")["T5"] == "CANNOT"


def test_conditional_prohibition_is_must_not_cannot():
    reader = HeuristicLicenseReader()
    result = reader.read_sentence(
        "You may not use the trademarks of the Licensor without specific prior "
        "written permission."
    )
    attitudes = {ta.term_id: ta.attitude for ta in result}
    assert attitudes.get("T11") == "MUST"


def test_sentence_without_terms_returns_nothing():
    reader = HeuristicLicenseReader()
    assert reader.read_sentence("This License shall be governed by the laws of California.") == []
