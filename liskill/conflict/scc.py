"""Inter-skill dynamic composition conflict detection over the Skill Composition Chain (§3.4.3).

An activation sequence ``s1, s2, ..., sn`` is organised by product containment
(eq. (11)): ``s(i+1)`` consumes the output of ``s(i)``, so the composite product
is outermost at the chain tail and innermost at the chain head.

    SCC = (V, E)   V = {s1..sn}
                   E = {(s(n), s(n-1)), (s(n-1), s(n-2)), ..., (s2, s1)}

The root is therefore the *consumer* (the tail, whose license is the outward
promise of the composite) and the leaf is the *producer* (the head, whose license
constrains the embedded part).  Judgement reuses Table 8 unchanged, walking the
edges from the innermost one outwards; a workflow conflicts as soon as one edge
conflicts (eq. (12)).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ..ontology import CONFLICT_TERMS
from ..schema import LEVEL_REPOSITORY, LEVEL_SKILL, LicenseProfile, SkillLicenseDoc
from .matrix import TermConflict, edge_conflicts
from .termdb import TermDatabase, merge_and_profiles, missing_profile

MISSING_LICENSE = "<missing>"


@dataclass
class SkillCompositionChain:
    """One workflow: an ordered activation sequence (eq. (11))."""

    workflow_id: str
    skill_ids: List[str]
    description: str = ""

    def edges(self):
        """Yield ``(index, consumer, producer)`` from the innermost edge outwards."""
        for index in range(len(self.skill_ids) - 1):
            yield index, self.skill_ids[index + 1], self.skill_ids[index]

    def __len__(self) -> int:
        return len(self.skill_ids)


@dataclass
class InterConflict:
    """One conflicting edge of a workflow."""

    workflow_id: str
    edge_index: int
    parent_skill: str          # consumer (downstream)
    child_skill: str           # producer (upstream)
    parent_license: str
    child_license: str
    term: TermConflict

    def to_dict(self) -> Dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "edge_index": self.edge_index,
            "parent_skill": self.parent_skill,
            "child_skill": self.child_skill,
            "parent_license": self.parent_license,
            "child_license": self.child_license,
            "term": self.term.to_dict(),
        }

    @property
    def pair(self) -> str:
        left, right = sorted((self.parent_license, self.child_license))
        return f"{left} & {right}"

    @property
    def edge(self) -> str:
        return f"{self.child_skill} -> {self.parent_skill}"


@dataclass
class WorkflowResult:
    """Detection outcome for one workflow (chain-level judgement of eq. (12))."""

    workflow_id: str
    skill_ids: List[str] = field(default_factory=list)
    conflicts: List[InterConflict] = field(default_factory=list)
    #: edges that could not be judged because one side declares no license
    undetermined_edges: int = 0

    @property
    def is_conflict(self) -> bool:
        return bool(self.conflicts)

    @property
    def conflict_edges(self) -> List[int]:
        """Distinct edge indices that carry at least one conflicting term."""
        return sorted({conflict.edge_index for conflict in self.conflicts})

    def to_dict(self) -> Dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "skill_ids": self.skill_ids,
            "conflict": self.is_conflict,
            "conflict_edges": self.conflict_edges,
            "undetermined_edges": self.undetermined_edges,
            "conflicts": [c.to_dict() for c in self.conflicts],
        }


class SCCDetector:
    """Edge-wise judgement of a composition chain."""

    def __init__(
        self,
        termdb: TermDatabase,
        docs: Dict[str, SkillLicenseDoc],
        terms: Optional[Sequence[str]] = None,
        strict_missing: bool = False,
    ) -> None:
        self.termdb = termdb
        self.docs = docs
        self.terms = list(terms) if terms is not None else list(CONFLICT_TERMS)
        #: when False (default) an edge touching a skill without any usable
        #: declaration is left *undetermined* instead of assuming "no grant"
        #: (rule D3), because an unknown license is not the same as a prohibition
        self.strict_missing = strict_missing

    # ------------------------------------------------------------------ helpers
    def resolve_node(self, skill_id: str):
        """§3.4.3 node license resolution: Skill level, then Repository level."""
        doc = self.docs.get(skill_id)
        if doc is None:
            return [MISSING_LICENSE], "Single"
        skill = doc.skill if doc.skill is not None and doc.skill.is_usable else None
        if skill is not None:
            return list(skill.license_ids), skill.licensing_type
        repo = doc.repo if doc.repo is not None and doc.repo.is_usable else None
        if repo is not None:
            return list(repo.license_ids), repo.licensing_type
        return [MISSING_LICENSE], "Single"

    def _profiles(self, skill_id: str) -> List[LicenseProfile]:
        licenses, licensing_type = self.resolve_node(skill_id)
        licenses = [lic for lic in licenses if lic]
        if not licenses or licenses == [MISSING_LICENSE]:
            return [missing_profile(self.terms)] if self.terms else [missing_profile()]
        if licensing_type == "Multi-OR" and len(licenses) > 1:
            return [self.termdb.profile(lic) for lic in licenses]
        if licensing_type == "Multi-AND" and len(licenses) > 1:
            return [merge_and_profiles([self.termdb.profile(lic) for lic in licenses])]
        return [self.termdb.profile(licenses[0])]

    def _evidence(self, skill_id: str) -> Dict[str, str]:
        licenses, _ = self.resolve_node(skill_id)
        if not licenses or licenses[0] == MISSING_LICENSE:
            return {}
        return {
            tid: ta.evidence
            for tid, ta in self.termdb.evidence(licenses[0]).items()
        }

    # -------------------------------------------------------------------- entry
    def detect(self, chain: SkillCompositionChain) -> WorkflowResult:
        result = WorkflowResult(workflow_id=chain.workflow_id, skill_ids=list(chain.skill_ids))
        if len(chain) < 2:
            return result
        for index, consumer, producer in chain.edges():
            parent_ids, _ = self.resolve_node(consumer)
            child_ids, _ = self.resolve_node(producer)
            missing_parent = parent_ids == [MISSING_LICENSE]
            missing_child = child_ids == [MISSING_LICENSE]
            if (missing_parent or missing_child) and not self.strict_missing:
                result.undetermined_edges += 1
                continue
            parent_profiles = self._profiles(consumer)
            child_profiles = self._profiles(producer)
            parent_ev = self._evidence(consumer)
            child_ev = self._evidence(producer)
            combos = [
                edge_conflicts(p_profile, c_profile, parent_ev, child_ev, self.terms)
                for p_profile in parent_profiles
                for c_profile in child_profiles
            ]
            if not combos or any(not combo for combo in combos):
                continue
            worst = max(combos, key=len)
            for conflict in worst:
                result.conflicts.append(
                    InterConflict(
                        workflow_id=chain.workflow_id,
                        edge_index=index,
                        parent_skill=consumer,
                        child_skill=producer,
                        parent_license=parent_ids[0],
                        child_license=child_ids[0],
                        term=conflict,
                    )
                )
        return result


def detect_inter(
    chains: Sequence[SkillCompositionChain],
    docs: Dict[str, SkillLicenseDoc],
    termdb: TermDatabase,
    terms: Optional[Sequence[str]] = None,
    strict_missing: bool = False,
) -> List[WorkflowResult]:
    """Run inter-skill detection over a batch of workflows."""
    detector = SCCDetector(termdb, docs, terms, strict_missing=strict_missing)
    return [detector.detect(chain) for chain in chains]
