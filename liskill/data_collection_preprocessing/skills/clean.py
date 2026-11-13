"""Two-stage preprocessing (§3.1.1).

**Invalid Record Filtering**
    ``name`` and ``description`` are mandatory; a SKILL.md body shorter than the
    minimum content length (50 characters, frontmatter excluded) is treated as a
    placeholder and dropped.

**Cross-platform Deduplication**
    the same skill is listed by several markets, so each record is keyed by
    ``SHA-256(name + description)``; on a collision only the record with the
    earliest collection timestamp is kept, and the hash becomes the global
    ``skill_id`` of the dataset.

The paper reports 2,027,275 raw records collapsing to 825,784 unique skills
(59.3% deduplication); the demo corpus reproduces the mechanism, not the scale.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from ...extract.frontmatter import body_text

#: §3.1.1 — SKILL.md bodies below this length are placeholders
MIN_BODY_CHARS = 50
#: length of the skill_id prefix taken from the digest
SKILL_ID_LENGTH = 16


@dataclass
class CleaningStats:
    raw_records: int = 0
    after_invalid_filter: int = 0
    after_dedup: int = 0

    @property
    def dedup_rate(self) -> float:
        if not self.after_invalid_filter:
            return 0.0
        removed = self.after_invalid_filter - self.after_dedup
        return round(100.0 * removed / self.after_invalid_filter, 2)

    def to_dict(self) -> Dict[str, float]:
        return {
            "raw_records": self.raw_records,
            "after_invalid_filter": self.after_invalid_filter,
            "after_dedup": self.after_dedup,
            "dedup_rate(%)": self.dedup_rate,
        }


def content_hash(name: str, description: str) -> str:
    """§3.1.1 — SHA-256 over the concatenation of name and description."""
    return hashlib.sha256(f"{name}{description}".encode("utf-8")).hexdigest()


def is_valid_record(record: Dict[str, object]) -> bool:
    """Invalid Record Filtering rule."""
    name = str(record.get("name") or "").strip()
    description = str(record.get("description") or "").strip()
    if not name or not description:
        return False
    body = body_text(str(record.get("skill_md_content") or ""))
    if body and len(body.strip()) < MIN_BODY_CHARS:
        return False
    return True


def deduplicate(records: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    """Keep the earliest collected record per content hash; assign ``skill_id``."""
    best: Dict[str, Dict[str, object]] = {}
    for record in records:
        digest = content_hash(
            str(record.get("name") or "").strip(), str(record.get("description") or "").strip()
        )
        collected_at = int(record.get("collected_at") or record.get("insert_data_time") or 0)
        candidate = dict(record)
        candidate["skill_id"] = f"{digest[:SKILL_ID_LENGTH]}"
        candidate["content_hash"] = digest
        current = best.get(digest)
        if current is None or collected_at < int(
            current.get("collected_at") or current.get("insert_data_time") or 0
        ):
            best[digest] = candidate
    return sorted(best.values(), key=lambda r: str(r.get("skill_id")))


def clean_records(
    records: Sequence[Dict[str, object]]
) -> tuple:
    """Run both stages; returns ``(unique_records, CleaningStats)``."""
    stats = CleaningStats(raw_records=len(records))
    kept = [record for record in records if is_valid_record(record)]
    stats.after_invalid_filter = len(kept)
    unique = deduplicate(kept)
    stats.after_dedup = len(unique)
    return unique, stats
