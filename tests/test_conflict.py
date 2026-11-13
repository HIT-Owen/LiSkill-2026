"""LST (§3.4.2) and SCC (§3.4.3) detection."""

import pytest

from liskill.conflict.lst import build_lst, detect_intra
from liskill.conflict.scc import SkillCompositionChain, detect_inter
from liskill.conflict.termdb import TermDatabase
from liskill.data_collection_preprocessing.licenses.reference import build_reference_set
from liskill.schema import (
    LEVEL_COMPONENT,
    LEVEL_REPOSITORY,
    LEVEL_SKILL,
    STATUS_MISSING,
    STATUS_VALID,
    NormalizedRecord,
    SkillLicenseDoc,
)


@pytest.fixture(scope="module")
def termdb() -> TermDatabase:
    return TermDatabase(build_reference_set()).build()


def record(license_ids, level, path=None, licensing_type="Single", status=STATUS_VALID):
    return NormalizedRecord(
        license_ids=list(license_ids),
        level=level,
        licensing_type=licensing_type,
        file_path=path,
        status=status,
        declaration_kind="Standard",
        resolved_from="inline",
    )


def test_lst_has_three_levels(termdb):
    doc = SkillLicenseDoc(
        "s1",
        repo=record(["Apache-2.0"], LEVEL_REPOSITORY),
        skill=record(["MIT"], LEVEL_SKILL),
        components=[record(["MIT"], LEVEL_COMPONENT, "scripts/a.py")],
    )
    root = build_lst(doc)
    assert root is not None and root.level == LEVEL_REPOSITORY
    assert root.children[0].level == LEVEL_SKILL
    assert root.children[0].children[0].file_path == "scripts/a.py"


def test_missing_level_is_skipped_and_edge_crosses_layers(termdb):
    doc = SkillLicenseDoc(
        "s2",
        repo=record(["MIT"], LEVEL_REPOSITORY),
        skill=record([], LEVEL_SKILL, status=STATUS_MISSING),
        components=[record(["GPL-3.0-only"], LEVEL_COMPONENT, "scripts/a.py")],
    )
    root = build_lst(doc)
    assert len(root.children) == 1
    assert root.children[0].level == LEVEL_COMPONENT
    conflicts = detect_intra([doc], termdb)
    assert conflicts
    assert conflicts[0].parent_level == LEVEL_REPOSITORY
    assert conflicts[0].child_level == LEVEL_COMPONENT


def test_no_lst_when_nothing_is_declared(termdb):
    doc = SkillLicenseDoc("s3", repo=record([], LEVEL_REPOSITORY, status=STATUS_MISSING))
    assert build_lst(doc) is None
    assert detect_intra([doc], termdb) == []


def test_permissive_tree_has_no_conflict(termdb):
    doc = SkillLicenseDoc(
        "s4",
        repo=record(["MIT"], LEVEL_REPOSITORY),
        skill=record(["MIT"], LEVEL_SKILL),
        components=[record(["Apache-2.0"], LEVEL_COMPONENT, "scripts/a.py")],
    )
    assert detect_intra([doc], termdb) == []


def test_copyleft_component_conflicts(termdb):
    doc = SkillLicenseDoc(
        "s5",
        repo=record(["MIT"], LEVEL_REPOSITORY),
        skill=record(["MIT"], LEVEL_SKILL),
        components=[record(["GPL-3.0-only"], LEVEL_COMPONENT, "scripts/render.py")],
    )
    conflicts = detect_intra([doc], termdb)
    terms = {c.term.term_id for c in conflicts}
    assert "T31" in terms and "T23" in terms
    assert all(c.child_path == "scripts/render.py" for c in conflicts)


def test_multi_or_conflicts_only_when_every_alternative_conflicts(termdb):
    # one alternative (MIT) is compatible with the child, so the edge is clean
    doc = SkillLicenseDoc(
        "s6",
        repo=record(["GPL-3.0-only", "MIT"], LEVEL_REPOSITORY, licensing_type="Multi-OR"),
        components=[record(["MIT"], LEVEL_COMPONENT, "scripts/a.py")],
    )
    assert detect_intra([doc], termdb) == []


def test_multi_and_aggregates_by_strictest(termdb):
    doc = SkillLicenseDoc(
        "s7",
        repo=record(["MIT", "GPL-3.0-only"], LEVEL_REPOSITORY, licensing_type="Multi-AND"),
        components=[record(["MIT"], LEVEL_COMPONENT, "scripts/a.py")],
    )
    # MIT AND GPL-3.0 behaves like GPL-3.0 as the parent -> permissive child is fine
    assert detect_intra([doc], termdb) == []


# --------------------------------------------------------------------------- #
# SCC
# --------------------------------------------------------------------------- #
def docs_map():
    return {
        "a": SkillLicenseDoc("a", skill=record(["MIT"], LEVEL_SKILL)),
        "b": SkillLicenseDoc("b", skill=record(["GPL-3.0-only"], LEVEL_SKILL)),
        "c": SkillLicenseDoc("c", skill=record(["MIT"], LEVEL_SKILL)),
    }


def test_chain_conflict_is_located_on_the_edge(termdb):
    chain = SkillCompositionChain("wf1", ["a", "b", "c"])
    results = detect_inter([chain], docs_map(), termdb)
    assert results[0].is_conflict
    # the tail (c, MIT) consumes b (GPL-3.0) -> conflict on edge 1
    assert {c.edge_index for c in results[0].conflicts} == {1}
    assert results[0].conflicts[0].parent_license == "MIT"
    assert results[0].conflicts[0].child_license == "GPL-3.0-only"


def test_single_skill_workflow_has_no_edge(termdb):
    results = detect_inter([SkillCompositionChain("wf2", ["a"])], docs_map(), termdb)
    assert results[0].is_conflict is False


def test_permissive_chain_is_clean(termdb):
    docs = {
        "x": SkillLicenseDoc("x", skill=record(["MIT"], LEVEL_SKILL)),
        "y": SkillLicenseDoc("y", skill=record(["Apache-2.0"], LEVEL_SKILL)),
    }
    assert detect_inter([SkillCompositionChain("wf3", ["x", "y"])], docs, termdb)[0].is_conflict is False


def test_undeclared_skill_leaves_the_edge_undetermined(termdb):
    docs = docs_map()
    docs["z"] = SkillLicenseDoc("z", skill=record([], LEVEL_SKILL, status=STATUS_MISSING))
    result = detect_inter([SkillCompositionChain("wf4", ["a", "z"])], docs, termdb)[0]
    assert result.is_conflict is False
    assert result.undetermined_edges == 1


def test_skill_level_overrides_repository_level(termdb):
    docs = {
        "p": SkillLicenseDoc("p", skill=record(["MIT"], LEVEL_SKILL)),
        "q": SkillLicenseDoc(
            "q",
            repo=record(["GPL-3.0-only"], LEVEL_REPOSITORY),
            skill=record(["MIT"], LEVEL_SKILL),
        ),
    }
    # q declares MIT at the Skill level, so the repository GPL does not apply
    assert detect_inter([SkillCompositionChain("wf5", ["p", "q"])], docs, termdb)[0].is_conflict is False
