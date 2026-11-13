"""Record schemas of the paper.

* :class:`SkillRecord`      — Table 4, the LiSkill-825k dataset document
* :class:`LicenseEntry`     — Table 5, the collected license reference entry
* :class:`NormalizedRecord` — Table 6, one normalized license declaration
* :class:`SkillLicenseDoc`  — §3.2.3, per-skill document holding the three levels

Plain dataclasses on purpose: the full pipeline has to run with the standard
library only, and every record round-trips to / from JSON so that the JSONL and
MongoDB sinks can share one representation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

# --------------------------------------------------------------------------- #
# enums (kept as plain strings so JSON round-trips are lossless)
# --------------------------------------------------------------------------- #
LEVEL_REPOSITORY = "Repository"
LEVEL_SKILL = "Skill"
LEVEL_COMPONENT = "Component"
LEVELS = (LEVEL_REPOSITORY, LEVEL_SKILL, LEVEL_COMPONENT)

LICENSING_SINGLE = "Single"
LICENSING_MULTI_OR = "Multi-OR"
LICENSING_MULTI_AND = "Multi-AND"
LICENSING_TYPES = (LICENSING_SINGLE, LICENSING_MULTI_OR, LICENSING_MULTI_AND)

KIND_STANDARD = "Standard"
KIND_CUSTOM = "Custom"
KIND_PROPRIETARY = "Proprietary"
KIND_COMMERCIAL = "Commercial"
KIND_REFER_LOCAL = "Refer-Local"
KIND_REFER_REPO = "Refer-Repo"
KIND_UNSPECIFIED = "Unspecified"
KIND_INVALID = "Invalid"
DECLARATION_KINDS = (
    KIND_STANDARD, KIND_CUSTOM, KIND_PROPRIETARY, KIND_COMMERCIAL,
    KIND_REFER_LOCAL, KIND_REFER_REPO, KIND_UNSPECIFIED, KIND_INVALID,
)

RESOLVED_GITHUB_API = "github-api"
RESOLVED_LOCAL_FILE = "local-file"
RESOLVED_REPO = "repo"
RESOLVED_INLINE = "inline"
RESOLVED_UNRESOLVED = "unresolved"

STATUS_VALID = "Valid"
STATUS_INVALID = "Invalid"
STATUS_MISSING = "Missing"
STATUSES = (STATUS_VALID, STATUS_INVALID, STATUS_MISSING)


# --------------------------------------------------------------------------- #
# Table 4 — LiSkill-825k dataset document
# --------------------------------------------------------------------------- #
@dataclass
class SkillRecord:
    """One unique skill of the benchmark dataset."""

    skill_id: str
    platform: str
    name: str
    description: str
    author: str = ""
    skill_md_content: str = ""
    skill_file_path: Optional[str] = None
    repo_license: Optional[str] = None
    repo_url: Optional[str] = None
    repo_full_name: Optional[str] = None
    default_branch: Optional[str] = None
    relative_path: Optional[str] = None
    file_path: Optional[str] = None
    #: epoch seconds of the first collection (used by the dedup rule)
    insert_data_time: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillRecord":
        names = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in names})


# --------------------------------------------------------------------------- #
# Table 5 — license reference entry
# --------------------------------------------------------------------------- #
@dataclass
class LicenseEntry:
    """One entry of the 4,996-item license reference set."""

    license_id: str
    full_name: str
    license_text: str = ""
    spdx_id: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    version: str = ""
    osi_approved: bool = False
    deprecated: bool = False
    text_sha256: str = ""
    sources: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_custom(self) -> bool:
        return self.license_id.upper().startswith("LIC-")

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LicenseEntry":
        names = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in names})


# --------------------------------------------------------------------------- #
# Table 6 — normalized license record
# --------------------------------------------------------------------------- #
@dataclass
class NormalizedRecord:
    """One normalized license declaration (Table 6).

    The model produces the first seven fields; the pipeline fills the remaining
    five when the record is stored.
    """

    license_ids: List[str] = field(default_factory=list)
    licensing_type: str = LICENSING_SINGLE
    declaration_kind: str = KIND_UNSPECIFIED
    exceptions: List[str] = field(default_factory=list)
    target_hint: Optional[str] = None
    evidence: str = ""
    confidence: float = 0.0
    # ---- filled by the pipeline ----
    raw_declaration: Optional[str] = None
    level: str = LEVEL_SKILL
    file_path: Optional[str] = None
    resolved_from: Optional[str] = None
    status: str = STATUS_MISSING

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NormalizedRecord":
        names = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in names})

    @property
    def is_usable(self) -> bool:
        """A record can take part in conflict detection only when Valid."""
        return self.status == STATUS_VALID and bool(self.license_ids)


# --------------------------------------------------------------------------- #
# §3.2.3 — per-skill license document
# --------------------------------------------------------------------------- #
@dataclass
class SkillLicenseDoc:
    """All license declarations of a single skill, grouped by carrier level."""

    skill_id: str
    repo: Optional[NormalizedRecord] = None
    skill: Optional[NormalizedRecord] = None
    components: List[NormalizedRecord] = field(default_factory=list)

    def records(self) -> List[NormalizedRecord]:
        out: List[NormalizedRecord] = []
        if self.repo is not None:
            out.append(self.repo)
        if self.skill is not None:
            out.append(self.skill)
        out.extend(self.components)
        return out

    def status(self) -> str:
        usable = [r for r in self.records() if r.is_usable]
        if usable:
            return STATUS_VALID
        if any(r.status == STATUS_INVALID for r in self.records()):
            return STATUS_INVALID
        return STATUS_MISSING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "licenses": {
                "repo": self.repo.to_dict() if self.repo else None,
                "skill": self.skill.to_dict() if self.skill else None,
                "components": [c.to_dict() for c in self.components],
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillLicenseDoc":
        licenses = data.get("licenses") or {}
        repo = licenses.get("repo")
        skill = licenses.get("skill")
        return cls(
            skill_id=data["skill_id"],
            repo=NormalizedRecord.from_dict(repo) if repo else None,
            skill=NormalizedRecord.from_dict(skill) if skill else None,
            components=[
                NormalizedRecord.from_dict(c) for c in licenses.get("components") or []
            ],
        )


# --------------------------------------------------------------------------- #
# derived semantic structures
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TermAttitude:
    """One (term, attitude) pair extracted from a sentence (paper eq. (1))."""

    term_id: str
    attitude: str
    evidence: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {"term_id": self.term_id, "attitude": self.attitude, "evidence": self.evidence}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TermAttitude":
        return cls(
            term_id=data["term_id"],
            attitude=data["attitude"],
            evidence=data.get("evidence", ""),
        )


#: license-level complete mapping l -> {term_id: attitude} (paper eq. (7))
LicenseProfile = Dict[str, str]

#: sentence-level observation set O_l(t) (paper eq. (6))
ObservationMap = Dict[str, List[str]]


def sort_terms(term_ids: Sequence[str]) -> List[str]:
    """Stable T1, T2, ... T31 ordering for reports."""
    def key(tid: str) -> int:
        try:
            return int(tid[1:])
        except (ValueError, IndexError):
            return 99
    return sorted(set(term_ids), key=key)
