"""Intra-skill cross-level conflict detection over the License Structure Tree (§3.4.2).

A skill is abstracted into a rooted tree ``LST = (V, E, Γ)``:

* the Repository record becomes the root,
* the Skill record becomes the intermediate layer,
* every Component record becomes a leaf,
* a level with ``status != Valid`` produces no node, so its scope is covered by
  the nearest valid ancestor and an edge may therefore skip a level,
* labels propagate downwards: an undeclared child inherits its nearest
  ancestor's license, while a Skill-level declaration overrides the inherited
  repository license.

Detection walks every parent/child edge bottom-up and applies Table 8 through
:func:`liskill.conflict.matrix.edge_conflicts`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..ontology import CONFLICT_TERMS
from ..schema import (
    LEVEL_COMPONENT,
    LEVEL_REPOSITORY,
    LEVEL_SKILL,
    NormalizedRecord,
    SkillLicenseDoc,
)
from .matrix import TermConflict, edge_conflicts
from .termdb import TermDatabase, merge_and_profiles

#: pseudo license id used for a node whose declaration is missing
MISSING_LICENSE = "<missing>"


@dataclass
class LSTNode:
    node_id: str
    level: str
    licenses: List[str]
    licensing_type: str = "Single"
    file_path: Optional[str] = None
    children: List["LSTNode"] = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass
class IntraConflict:
    """One conflicting parent/child license pair inside a single skill."""

    skill_id: str
    parent_level: str
    child_level: str
    parent_license: str
    child_license: str
    term: TermConflict
    child_path: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "skill_id": self.skill_id,
            "parent_level": self.parent_level,
            "child_level": self.child_level,
            "parent_license": self.parent_license,
            "child_license": self.child_license,
            "term": self.term.to_dict(),
            "child_path": self.child_path,
        }

    @property
    def pair(self) -> str:
        return f"{self.parent_license} -> {self.child_license}"


def _node_from_record(record: NormalizedRecord, node_id: str) -> LSTNode:
    return LSTNode(
        node_id=node_id,
        level=record.level,
        licenses=list(record.license_ids),
        licensing_type=record.licensing_type,
        file_path=record.file_path,
    )


def build_lst(doc: SkillLicenseDoc) -> Optional[LSTNode]:
    """Build the License Structure Tree of one skill (``None`` when unusable)."""
    repo = doc.repo if doc.repo is not None and doc.repo.is_usable else None
    skill = doc.skill if doc.skill is not None and doc.skill.is_usable else None
    components = [c for c in doc.components if c.is_usable]

    if repo is None and skill is None and not components:
        return None

    pending = list(components)
    if repo is not None:
        root = _node_from_record(repo, f"{doc.skill_id}:{LEVEL_REPOSITORY}")
    elif skill is not None:
        root = _node_from_record(skill, f"{doc.skill_id}:{LEVEL_SKILL}")
    else:  # only components declare a license: the first one anchors the tree
        root = _node_from_record(pending.pop(0), f"{doc.skill_id}:{LEVEL_COMPONENT}:root")

    anchor = root
    if skill is not None and repo is not None:
        anchor = _node_from_record(skill, f"{doc.skill_id}:{LEVEL_SKILL}")
        root.children.append(anchor)

    for component in pending:
        anchor.children.append(
            _node_from_record(
                component,
                f"{doc.skill_id}:{LEVEL_COMPONENT}:{component.file_path or 'inline'}",
            )
        )
    return root


class LSTDetector:
    """Bottom-up edge judgement with multi-license support."""

    def __init__(self, termdb: TermDatabase, terms: Optional[Sequence[str]] = None) -> None:
        self.termdb = termdb
        self.terms = list(terms) if terms is not None else list(CONFLICT_TERMS)

    # ------------------------------------------------------------------ helpers
    def _profiles(self, node: LSTNode) -> List[Dict[str, str]]:
        """Multi-OR yields one profile per alternative; Multi-AND merges by ⊙."""
        licenses = [lic for lic in node.licenses if lic]
        if not licenses:
            return []
        if node.licensing_type == "Multi-OR" and len(licenses) > 1:
            return [self.termdb.profile(lic) for lic in licenses]
        if node.licensing_type == "Multi-AND" and len(licenses) > 1:
            return [merge_and_profiles([self.termdb.profile(lic) for lic in licenses])]
        return [self.termdb.profile(licenses[0])]

    def _evidence(self, node: LSTNode) -> Dict[str, str]:
        if not node.licenses:
            return {}
        primary = node.licenses[0]
        return {tid: ta.evidence for tid, ta in self.termdb.evidence(primary).items()}

    def _edge(self, skill_id: str, parent: LSTNode, child: LSTNode) -> List[IntraConflict]:
        parent_profiles = self._profiles(parent)
        child_profiles = self._profiles(child)
        if not parent_profiles or not child_profiles:
            return []
        parent_ids = parent.licenses or [MISSING_LICENSE]
        child_ids = child.licenses or [MISSING_LICENSE]
        parent_ev = self._evidence(parent)
        child_ev = self._evidence(child)

        # Multi-OR: the edge is only conflictual when *every* alternative conflicts
        combos: List[List[TermConflict]] = []
        for p_profile in parent_profiles:
            for c_profile in child_profiles:
                combos.append(
                    edge_conflicts(p_profile, c_profile, parent_ev, child_ev, self.terms)
                )
        if not combos or any(not combo for combo in combos):
            return []
        worst = max(combos, key=len)
        return [
            IntraConflict(
                skill_id=skill_id,
                parent_level=parent.level,
                child_level=child.level,
                parent_license=parent_ids[0],
                child_license=child_ids[0],
                term=conflict,
                child_path=child.file_path,
            )
            for conflict in worst
        ]

    # -------------------------------------------------------------------- entry
    def detect(self, doc: SkillLicenseDoc) -> List[IntraConflict]:
        root = build_lst(doc)
        if root is None:
            return []
        conflicts: List[IntraConflict] = []
        for parent in root.walk():
            for child in parent.children:
                conflicts.extend(self._edge(doc.skill_id, parent, child))
        return conflicts


def detect_intra(
    docs: Sequence[SkillLicenseDoc],
    termdb: TermDatabase,
    terms: Optional[Sequence[str]] = None,
) -> List[IntraConflict]:
    """Run intra-skill detection over a batch of skills."""
    detector = LSTDetector(termdb, terms)
    out: List[IntraConflict] = []
    for doc in docs:
        out.extend(detector.detect(doc))
    return out
