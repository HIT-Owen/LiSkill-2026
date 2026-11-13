"""License term database (§3.4.1).

For every license `l` of the reference set the reader produces sentence-level
observations ``O_l(t)`` (eq. (6)); the aggregation operator ⊙ of Table 7 folds
them into the license-level mapping ``Λ_l`` (eq. (7)).  Terms that the license
never mentions are completed by the default rules A1–A3 / D1–D3.

The database is the only thing the detectors read: once built, no license text
is consulted again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..ontology import (
    OBLIGATION_TERMS,
    RE_GRANT_CUE,
    RIGHT_TERMS,
    TERM_BY_ID,
    TERMS,
    strictest,
)
from ..data_collection_preprocessing.licenses.reference import ReferenceSet
from ..schema import LicenseProfile, ObservationMap, TermAttitude
from ..understand.reader import HeuristicLicenseReader, LicenseReader

#: D1 — no explicit requirement constitutes no obligation
DEFAULT_OBLIGATION_ATTITUDE = "CAN"
#: D2 / D3 — rights depend on whether the license gives a catch-all grant
DEFAULT_GRANTED_ATTITUDE = "CAN"
DEFAULT_WITHOUT_GRANT_ATTITUDE = "CANNOT"


class TermDatabase:
    """Term-bounded semantic representation of every license (eq. (8))."""

    def __init__(
        self,
        reference: ReferenceSet,
        reader: Optional[LicenseReader] = None,
        terms: Iterable[str] = tuple(t.tid for t in TERMS),
    ) -> None:
        self.reference = reference
        self.reader = reader or HeuristicLicenseReader()
        self.terms: List[str] = list(terms)
        self.observations: Dict[str, ObservationMap] = {}
        self.grants: Dict[str, bool] = {}
        self.profiles: Dict[str, LicenseProfile] = {}

    # ---------------------------------------------------------------- building
    def build(self, license_ids: Optional[Iterable[str]] = None) -> "TermDatabase":
        ids = list(license_ids) if license_ids is not None else list(self.reference.entries)
        for license_id in ids:
            entry = self.reference.get(license_id)
            if entry is None:
                continue
            text = entry.license_text or ""
            observations: ObservationMap = {}
            observer = getattr(self.reader, "observe", None)
            if observer is not None:
                observations = observer(text)
            else:  # model-backed reader: aggregate per sentence ourselves
                for ta in self.reader.read_text(text):
                    observations.setdefault(ta.term_id, []).append(ta.attitude)
            self.observations[license_id] = observations
            self.grants[license_id] = self._detect_grant(text, observations)
            self.profiles[license_id] = self._complete(license_id)
        return self

    def _detect_grant(self, text: str, observations: ObservationMap) -> bool:
        """Grant(l) of Table 7.

        The paper defines it through an open-ended catch-all qualifier
        ("without restriction", "for any purpose", ...).  Text-only licenses may
        instead enumerate a broad right set without such a qualifier; a license
        that explicitly grants at least two right-class terms is treated the same
        way, which keeps rule D3 targeted at genuinely silent declarations.
        """
        if RE_GRANT_CUE.search(text or ""):
            return True
        granted_rights = sum(
            1
            for tid in observations
            if tid in RIGHT_TERMS and "CAN" in observations[tid]
        )
        return granted_rights >= 2

    def _complete(self, license_id: str) -> LicenseProfile:
        observations = self.observations.get(license_id, {})
        grant = self.grants.get(license_id, False)
        profile: LicenseProfile = {}
        for tid in self.terms:
            observed = observations.get(tid) or []
            if observed:
                aggregated = strictest(observed)
                assert aggregated is not None
                profile[tid] = aggregated
                continue
            if tid in OBLIGATION_TERMS:
                profile[tid] = DEFAULT_OBLIGATION_ATTITUDE
            else:
                profile[tid] = (
                    DEFAULT_GRANTED_ATTITUDE if grant else DEFAULT_WITHOUT_GRANT_ATTITUDE
                )
        return profile

    # ----------------------------------------------------------------- lookup
    def profile(self, license_id: str) -> LicenseProfile:
        cached = self.profiles.get(license_id)
        if cached is not None:
            return cached
        entry = self.reference.get(license_id)
        text = entry.license_text if entry else ""
        observations = {}
        observer = getattr(self.reader, "observe", None)
        if observer is not None and text:
            observations = observer(text)
        self.observations[license_id] = observations
        self.grants[license_id] = self._detect_grant(text, observations)
        self.profiles[license_id] = self._complete(license_id)
        return self.profiles[license_id]

    def observe(self, license_id: str) -> ObservationMap:
        if license_id not in self.observations:
            self.profile(license_id)
        return self.observations[license_id]

    def evidence(self, license_id: str) -> Dict[str, TermAttitude]:
        entry = self.reference.get(license_id)
        if entry is None:
            return {}
        observer = getattr(self.reader, "read_text", None)
        if observer is None:
            return {}
        return {ta.term_id: ta for ta in observer(entry.license_text or "")}

    def grant(self, license_id: str) -> bool:
        if license_id not in self.grants:
            self.profile(license_id)
        return self.grants.get(license_id, False)

    def is_known(self, license_id: str) -> bool:
        return license_id in self.reference.entries

    # ------------------------------------------------------------- serializing
    def to_dict(self) -> Dict[str, object]:
        return {
            "terms": self.terms,
            "grants": self.grants,
            "profiles": self.profiles,
            "observations": self.observations,
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path, reference: ReferenceSet) -> "TermDatabase":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        db = cls(reference, terms=data.get("terms") or [t.tid for t in TERMS])
        db.grants = data.get("grants", {})
        db.profiles = data.get("profiles", {})
        db.observations = data.get("observations", {})
        return db

    # ---------------------------------------------------------------- reporting
    def summary(self, license_id: str) -> str:
        profile = self.profile(license_id)
        return " ".join(
            f"{tid}={profile[tid]}"
            for tid in sorted(profile, key=lambda t: int(t[1:]))
        )

    def describe(self, license_id: str) -> str:
        entry = self.reference.get(license_id)
        name = entry.full_name if entry else license_id
        return f"{license_id} ({name}) grant={int(self.grant(license_id))}"


def missing_profile(terms: Iterable[str] = tuple(t.tid for t in TERMS)) -> LicenseProfile:
    """Profile of a skill that declares no usable license at all.

    §3.4.3: "两层均缺失时，按表 7 的缺省规则处理".  Without any declaration there
    is no grant (D3), so every right defaults to CANNOT while obligations stay
    unenforceable (D1).
    """
    profile: LicenseProfile = {}
    for tid in terms:
        profile[tid] = (
            DEFAULT_OBLIGATION_ATTITUDE if tid in OBLIGATION_TERMS else "CANNOT"
        )
    return profile


def merge_and_profiles(profiles: List[LicenseProfile]) -> LicenseProfile:
    """Multi-AND: the node is bound by every license, aggregated by ⊙."""
    merged: LicenseProfile = {}
    for tid in TERM_BY_ID:
        values = [p[tid] for p in profiles if tid in p]
        if values:
            merged[tid] = strictest(values)  # type: ignore[assignment]
    return merged
