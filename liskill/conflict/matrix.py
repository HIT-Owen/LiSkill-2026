"""License compatibility matrix (Table 8) and edge judgement (eq. (9)–(10)).

The matrix is directional: the row is the *parent* (the whole work, which makes
the distribution promise) and the column is the *child* (the embedded
component, which restricts that promise).

    parent \\ child | CAN          | MUST      | CANNOT
    -------------- | ------------ | --------- | ------------
    CAN            | No conflict  | Conflict  | Conflict
    MUST           | No conflict  | Depends   | Conflict
    CANNOT         | No conflict  | Conflict  | No conflict

``Depends`` is resolved by the condition-entailment check ``E`` described in
§3.4.2: two MUSTs on the same term are compatible when the conditions they
attach are identical / subsumed, and conflicting when they are mutually
exclusive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from ..ontology import ATTITUDE_RANK, RE_CONDITION_MARKER, TERM_BY_ID
from ..schema import LicenseProfile

NO_CONFLICT = "No conflict"
CONFLICT = "Conflict"
DEPENDS = "Depends"

COMPATIBILITY_MATRIX: Dict[Tuple[str, str], str] = {
    ("CAN", "CAN"): NO_CONFLICT,
    ("CAN", "MUST"): CONFLICT,
    ("CAN", "CANNOT"): CONFLICT,
    ("MUST", "CAN"): NO_CONFLICT,
    ("MUST", "MUST"): DEPENDS,
    ("MUST", "CANNOT"): CONFLICT,
    ("CANNOT", "CAN"): NO_CONFLICT,
    ("CANNOT", "MUST"): CONFLICT,
    ("CANNOT", "CANNOT"): NO_CONFLICT,
}

_MUTUAL_EXCLUSION = re.compile(
    r"\bnot\b|\bno\b|\bprohibit\w*|\bwithout\b|\bnever\b", re.IGNORECASE
)


def lookup(parent: str, child: str) -> str:
    """Table-8 look-up for one term."""
    try:
        return COMPATIBILITY_MATRIX[(parent, child)]
    except KeyError as exc:  # pragma: no cover - guarded by the enum
        raise ValueError(f"unknown attitude pair: {(parent, child)!r}") from exc


def extract_conditions(evidence: str) -> Set[str]:
    """Pull the condition clause out of a MUST statement (function ``E`` input)."""
    if not evidence:
        return set()
    match = RE_CONDITION_MARKER.search(evidence)
    if not match:
        return set()
    tail = evidence[match.start():].strip()
    tail = re.split(r"[.;]", tail, maxsplit=1)[0]
    return {" ".join(tail.lower().split())} if tail else set()


def conditions_compatible(parent_conditions: Set[str], child_conditions: Set[str]) -> bool:
    """``E`` — do the two condition sets hold simultaneously?

    Identical or empty condition sets are compatible.  When the texts differ we
    only report exclusivity if one side negates what the other demands, which is
    the conservative reading of §3.4.2 ("条件一致或兼容则不冲突，互斥则冲突").
    """
    if not parent_conditions or not child_conditions:
        return True
    if parent_conditions == child_conditions:
        return True
    p_text = " ".join(sorted(parent_conditions))
    c_text = " ".join(sorted(child_conditions))
    if p_text == c_text:
        return True
    p_neg = bool(_MUTUAL_EXCLUSION.search(p_text))
    c_neg = bool(_MUTUAL_EXCLUSION.search(c_text))
    if p_neg == c_neg:
        return True
    # one side demands a condition the other forbids: strip the negation words
    # and compare the residual obligations
    p_core = _MUTUAL_EXCLUSION.sub(" ", p_text).split()
    c_core = _MUTUAL_EXCLUSION.sub(" ", c_text).split()
    shared = set(p_core) & set(c_core)
    return not shared


@dataclass(frozen=True)
class TermConflict:
    """One conflicting (parent, child, term) judgement."""

    term_id: str
    parent_attitude: str
    child_attitude: str
    relation: str
    parent_evidence: str = ""
    child_evidence: str = ""

    @property
    def term_name(self) -> str:
        term = TERM_BY_ID.get(self.term_id)
        return term.name if term else self.term_id

    def to_dict(self) -> Dict[str, str]:
        return {
            "term_id": self.term_id,
            "term_name": self.term_name,
            "parent_attitude": self.parent_attitude,
            "child_attitude": self.child_attitude,
            "relation": self.relation,
            "parent_evidence": self.parent_evidence,
            "child_evidence": self.child_evidence,
        }


def judge_term(
    term_id: str,
    parent_attitude: str,
    child_attitude: str,
    parent_evidence: str = "",
    child_evidence: str = "",
) -> Optional[TermConflict]:
    """Eq. (10): conflict indicator for a single term on a single edge."""
    relation = lookup(parent_attitude, child_attitude)
    if relation == DEPENDS:
        compatible = conditions_compatible(
            extract_conditions(parent_evidence), extract_conditions(child_evidence)
        )
        if compatible:
            return None
    elif relation == NO_CONFLICT:
        return None
    return TermConflict(
        term_id=term_id,
        parent_attitude=parent_attitude,
        child_attitude=child_attitude,
        relation=relation,
        parent_evidence=parent_evidence,
        child_evidence=child_evidence,
    )


def edge_conflicts(
    parent_profile: LicenseProfile,
    child_profile: LicenseProfile,
    parent_evidence: Optional[Dict[str, str]] = None,
    child_evidence: Optional[Dict[str, str]] = None,
    terms: Optional[Sequence[str]] = None,
) -> List[TermConflict]:
    """Eq. (9)–(10) over all terms of the intersection ``T_p ∩ T_c``."""
    parent_evidence = parent_evidence or {}
    child_evidence = child_evidence or {}
    candidates = terms if terms is not None else sorted(
        set(parent_profile) & set(child_profile), key=lambda t: int(t[1:])
    )
    conflicts: List[TermConflict] = []
    for tid in candidates:
        p_att = parent_profile.get(tid)
        c_att = child_profile.get(tid)
        if p_att is None or c_att is None:
            continue
        found = judge_term(
            tid, p_att, c_att, parent_evidence.get(tid, ""), child_evidence.get(tid, "")
        )
        if found is not None:
            conflicts.append(found)
    return conflicts


def strongest_term(conflicts: Sequence[TermConflict]) -> Optional[TermConflict]:
    """Pick the term with the widest attitude gap, for compact reporting."""
    if not conflicts:
        return None
    return max(
        conflicts,
        key=lambda c: (
            ABSOLUTE_GAP(c),
            -int(c.term_id[1:]),
        ),
    )


def ABSOLUTE_GAP(conflict: TermConflict) -> int:
    return abs(
        ATTITUDE_RANK[conflict.parent_attitude] - ATTITUDE_RANK[conflict.child_attitude]
    )
