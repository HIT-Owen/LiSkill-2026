"""Aggregations behind RQ1–RQ3 (§4.2–§4.4).

Every function returns plain dictionaries so that both the markdown report and
the JSON dump can reuse them.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Optional, Sequence

from ..conflict.lst import IntraConflict
from ..conflict.scc import WorkflowResult
from ..schema import (
    STATUS_INVALID,
    STATUS_MISSING,
    STATUS_VALID,
    NormalizedRecord,
    SkillLicenseDoc,
)
from ..ontology import TERM_BY_ID

# --------------------------------------------------------------------------- #
# RQ1 — coverage and composition
# --------------------------------------------------------------------------- #
def _declaration(
    doc: SkillLicenseDoc, usable_only: bool = True
) -> Optional[NormalizedRecord]:
    """The one declaration a skill contributes to the RQ1 statistics.

    Skill level first, then Repository (§3.4.3 node resolution), then a Component
    record.  Counting all three levels instead lets component headers dominate.
    """
    for record in (doc.skill, doc.repo):
        if record is not None and (record.is_usable or not usable_only):
            return record
    for record in doc.components:
        if record is not None and (record.is_usable or not usable_only):
            return record
    return None


def rq1_coverage(docs: Sequence[SkillLicenseDoc]) -> Dict[str, object]:
    total = len(docs)
    valid = sum(1 for doc in docs if doc.status() == STATUS_VALID)
    invalid = sum(1 for doc in docs if doc.status() == STATUS_INVALID)
    missing = total - valid - invalid
    def pct(value: int) -> float:
        return round(100.0 * value / total, 2) if total else 0.0
    return {
        "total": total,
        "rows": [
            {"category": "Valid Declaration", "count": valid, "percentage": pct(valid)},
            {"category": "Invalid Declaration", "count": invalid, "percentage": pct(invalid)},
            {"category": "Missing Declaration", "count": missing, "percentage": pct(missing)},
        ],
    }


def rq1_license_composition(
    docs: Sequence[SkillLicenseDoc], top_n: int = 10
) -> Dict[str, object]:
    """Valid standard licenses vs. custom registrations (Table 10).

    Table 10 is a distribution over *skills*, so each skill contributes exactly
    one declaration: its Skill-level record, falling back to the Repository level
    (the node resolution of §3.4.3) and finally to a Component record.  Counting
    all three levels instead would let component headers dominate the mix.
    """
    counter: Counter = Counter()
    custom = 0
    valid_declarations = 0
    for doc in docs:
        record = _declaration(doc)
        if record is None:
            continue
        valid_declarations += 1
        is_custom = False
        for license_id in record.license_ids:
            if license_id.upper().startswith("LIC-"):
                is_custom = True
            else:
                counter[license_id] += 1
        if is_custom:
            custom += 1
    total = valid_declarations or 1
    rows = [
        {
            "license": license_id,
            "count": count,
            "percentage": round(100.0 * count / total, 2),
        }
        for license_id, count in counter.most_common(top_n)
    ]
    return {
        "standard_total": sum(counter.values()),
        "standard_distinct": len(counter),
        "declarations": valid_declarations,
        "custom_total": custom,
        "custom_ratio": round(100.0 * custom / total, 2),
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# RQ3 — conflict scale and shape
# --------------------------------------------------------------------------- #
def intra_summary(
    conflicts: Sequence[IntraConflict], docs: Sequence[SkillLicenseDoc]
) -> Dict[str, object]:
    conflicting_skills = {c.skill_id for c in conflicts}
    total = len(docs) or 1
    pair_counter = Counter(c.pair for c in conflicts)
    term_counter = Counter(c.term.term_id for c in conflicts)
    level_counter = Counter(f"{c.parent_level}->{c.child_level}" for c in conflicts)
    return {
        "skills": len(docs),
        "conflict_skills": len(conflicting_skills),
        "conflict_skill_rate": round(100.0 * len(conflicting_skills) / total, 2),
        "conflict_issues": len(conflicts),
        "top_pairs": [
            {"pair": pair, "count": count, "percentage": round(100.0 * count / (len(conflicts) or 1), 2)}
            for pair, count in pair_counter.most_common(10)
        ],
        "top_terms": [
            {
                "term_id": tid,
                "term_name": TERM_BY_ID[tid].name if tid in TERM_BY_ID else tid,
                "count": count,
                "percentage": round(100.0 * count / (len(conflicts) or 1), 2),
            }
            for tid, count in term_counter.most_common(10)
        ],
        "level_pairs": [
            {"levels": name, "count": count} for name, count in level_counter.most_common()
        ],
    }


def inter_summary(results: Sequence[WorkflowResult]) -> Dict[str, object]:
    workflows = len(results) or 1
    conflicting = [r for r in results if r.is_conflict]
    edges = sum(max(0, len(r.skill_ids) - 1) for r in results)
    conflict_edge_ids = {
        (r.workflow_id, index) for r in results for index in r.conflict_edges
    }
    conflict_terms = [c for r in results for c in r.conflicts]
    pair_counter = Counter(c.pair for c in conflict_terms)
    term_counter = Counter(c.term.term_id for c in conflict_terms)
    return {
        "workflows": len(results),
        "conflict_workflows": len(conflicting),
        "conflict_workflow_rate": round(100.0 * len(conflicting) / workflows, 2),
        "edges": edges,
        "conflict_edges": len(conflict_edge_ids),
        "conflict_edge_rate": round(100.0 * len(conflict_edge_ids) / (edges or 1), 2),
        "undetermined_edges": sum(r.undetermined_edges for r in results),
        "conflict_terms": len(conflict_terms),
        "avg_chain_length": round(
            sum(len(r.skill_ids) for r in results) / workflows, 2
        ),
        "top_pairs": [
            {
                "pair": pair,
                "count": count,
                "percentage": round(100.0 * count / (len(conflict_terms) or 1), 2),
            }
            for pair, count in pair_counter.most_common(10)
        ],
        "top_terms": [
            {
                "term_id": tid,
                "term_name": TERM_BY_ID[tid].name if tid in TERM_BY_ID else tid,
                "count": count,
                "percentage": round(100.0 * count / (len(conflict_terms) or 1), 2),
            }
            for tid, count in term_counter.most_common(10)
        ],
    }


def declaration_kind_distribution(docs: Sequence[SkillLicenseDoc]) -> List[Dict[str, object]]:
    """Shape of the declaration each skill actually carries (one row per skill).

    The kind comes from the record that determines the skill's status; for a
    skill with no usable declaration it comes from the record that made it
    Missing or Invalid, so the rows always sum to the analysed skill count.
    """
    counter: Counter = Counter()
    for doc in docs:
        record = _declaration(doc) or _declaration(doc, usable_only=False)
        counter[record.declaration_kind if record is not None else "Unspecified"] += 1
    total = sum(counter.values()) or 1
    return [
        {"kind": kind, "count": count, "percentage": round(100.0 * count / total, 2)}
        for kind, count in counter.most_common()
    ]
