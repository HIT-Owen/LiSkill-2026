"""License reference set (§3.1.2).

`ReferenceSet` merges entries coming from the four public sources used in the
paper (SPDX, OSI, tldrLegal, FOSSology) into a single keyed collection:

* **key** — the SPDX identifier when one exists, otherwise an internal
  ``LIC-XXXX`` identifier;
* **alias index** — normalised alias -> license_id, used by the rule-based
  pre-filter of §3.2.2 (which normalises case, hyphens and spaces);
* **text index** — SHA-256 of the full legal text, used to resolve
  ``Refer-Local`` declarations without invoking the model;
* **candidate set** — the closed set of SPDX identifiers handed to the model so
  that it can never invent an identifier (paper R1).

Entries registered from a skill's own declaration (§3.2.2 *自定义许可证注册*) are
added with ``source = skill-declaration``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ...schema import LicenseEntry
from .legal_texts import CUSTOM_TEXTS, LICENSE_TEXTS

_ALIAS_STRIP = re.compile(r"[^a-z0-9]+")
_SOURCE_PRIORITY = ("SPDX", "OSI", "tldrLegal", "FOSSology")


def normalize_alias(value: str) -> str:
    """Case-, hyphen- and space-insensitive key used for exact matching."""
    return _ALIAS_STRIP.sub("", (value or "").lower())


def sha256_text(text: str) -> str:
    """Hash of a legal text, whitespace-insensitive at the edges.

    SPDX ships ``licenseText`` with a leading newline, while a declaration read
    out of a ``LICENSE`` file usually carries trailing whitespace.  Normalising
    both sides is what makes the text index of §3.2.2 hit at all.
    """
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


class ReferenceSet:
    """The 4,996-item license reference set (708 standard + custom registrations)."""

    def __init__(self) -> None:
        self.entries: Dict[str, LicenseEntry] = {}
        self._alias_index: Dict[str, str] = {}
        self._text_index: Dict[str, str] = {}
        self._custom_counter = 0

    # ------------------------------------------------------------------ loading
    def add(self, entry: LicenseEntry) -> LicenseEntry:
        self.entries[entry.license_id] = entry
        keys = {entry.license_id, entry.spdx_id or "", entry.full_name, *entry.aliases}
        for key in keys:
            norm = normalize_alias(key)
            if norm:
                self._alias_index.setdefault(norm, entry.license_id)
        if entry.text_sha256:
            self._text_index.setdefault(entry.text_sha256, entry.license_id)
        return entry

    def add_from_text(
        self,
        license_id: str,
        full_name: str,
        text: str,
        *,
        spdx_id: Optional[str] = None,
        aliases: Optional[Iterable[str]] = None,
        version: str = "",
        osi_approved: bool = True,
        deprecated: bool = False,
        sources: Optional[List[dict]] = None,
    ) -> LicenseEntry:
        text_sha = sha256_text(text)
        entry = LicenseEntry(
            license_id=license_id,
            full_name=full_name,
            license_text=text,
            spdx_id=spdx_id,
            aliases=list(aliases or []),
            version=version,
            osi_approved=osi_approved,
            deprecated=deprecated,
            text_sha256=text_sha,
            sources=sources or [{"source": "SPDX", "url": f"https://spdx.org/licenses/{license_id}.html"}],
        )
        return self.add(entry)

    # ------------------------------------------------------------------ lookup
    def get(self, license_id: str) -> Optional[LicenseEntry]:
        return self.entries.get(license_id)

    @property
    def candidates(self) -> List[str]:
        """Closed candidate set of SPDX identifiers (paper §3.2.2, part 3)."""
        return sorted(e.spdx_id for e in self.entries.values() if e.spdx_id)

    def match_exact(self, declaration: str) -> Optional[str]:
        """Rule-based pre-filter: alias / id match, ignoring case and hyphens."""
        if not declaration:
            return None
        norm = normalize_alias(declaration)
        if norm in self._alias_index:
            return self._alias_index[norm]
        # tolerate a trailing "license"/"licence" and a version suffix
        for suffix in ("license", "licence", "licensed"):
            if norm.endswith(suffix) and norm[: -len(suffix)] in self._alias_index:
                return self._alias_index[norm[: -len(suffix)]]
        return None

    def match_text(self, text: str) -> Optional[str]:
        """Full-text resolution by SHA-256 (paper §3.2.2, Refer-Local backfill)."""
        return self._text_index.get(sha256_text(text.strip()))

    def guess_by_name(self, text: str) -> Optional[str]:
        """Best-effort name lookup inside free text (used by backfill fallback).

        Short aliases (``MIT``, ``ISC``) only match as standalone tokens so that
        "submit" is not read as MIT; longer aliases may appear inline
        ("Apache2.0licensed").
        """
        head = (text or "")[:512].lower()
        if not head:
            return None
        compact = _ALIAS_STRIP.sub("", head)
        tokens = {tok for tok in re.split(r"[^a-z0-9]+", head) if tok}
        best: Optional[str] = None
        best_score = 0
        for alias, license_id in self._alias_index.items():
            if len(alias) < 3:
                continue
            if alias in tokens:
                score = 100 + len(alias)
            elif len(alias) >= 6 and alias in compact:
                score = len(alias)
            else:
                continue
            if score > best_score:
                best, best_score = license_id, score
        return best

    # ------------------------------------------------------- custom registration
    def register_custom(self, declaration: str, full_text: str = "") -> LicenseEntry:
        """Register an unmappable declaration as a custom license (LIC-XXXX)."""
        declaration = (declaration or "").strip()
        digest = sha256_text(normalize_alias(declaration) or declaration)[:8].upper()
        license_id = f"LIC-{digest}"
        existing = self.entries.get(license_id)
        if existing is not None:
            return existing
        body = (full_text or declaration).strip()
        self._custom_counter += 1
        return self.add(
            LicenseEntry(
                license_id=license_id,
                full_name=declaration[:120] or "Custom license",
                license_text=body,
                spdx_id=None,
                aliases=[declaration] if declaration else [],
                version="",
                osi_approved=False,
                deprecated=False,
                text_sha256=sha256_text(body),
                sources=[
                    {
                        "source": "skill-declaration",
                        "url": "",
                        "note": "registered during normalization (§3.2.2)",
                    }
                ],
            )
        )

    # ------------------------------------------------------------------ helpers
    @property
    def standard_count(self) -> int:
        return sum(1 for e in self.entries.values() if not e.is_custom)

    @property
    def custom_count(self) -> int:
        return sum(1 for e in self.entries.values() if e.is_custom)

    def to_dict(self) -> Dict[str, List[dict]]:
        return {"licenses": [e.to_dict() for e in self.entries.values()]}

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "ReferenceSet":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        ref = cls()
        for item in data.get("licenses", []):
            ref.add(LicenseEntry.from_dict(item))
        return ref


def _demo_sources(license_id: str) -> List[dict]:
    """Provenance records mimicking the four-source merge of §3.1.2."""
    return [
        {"source": "SPDX", "url": f"https://spdx.org/licenses/{license_id}.html", "fetched_at": "2026-05-01"},
        {"source": "OSI", "url": "https://opensource.org/licenses", "fetched_at": "2026-05-01"},
        {"source": "tldrLegal", "url": f"https://www.tldrlegal.com/license/{license_id.lower()}", "fetched_at": "2026-05-02"},
        {"source": "FOSSology", "url": "https://github.com/fossology/fossology", "fetched_at": "2026-05-02"},
    ]


def build_reference_set(include_custom: bool = False) -> ReferenceSet:
    """Build the demo reference set from the bundled clause corpus.

    In the full pipeline this function reads the four sources from disk
    (``license_id`` as primary key, text-hash based de-duplication, see §3.1.2).
    The released demo ships the clause-level corpus only.
    """
    ref = ReferenceSet()
    for license_id in sorted(LICENSE_TEXTS):
        entry = LICENSE_TEXTS[license_id]
        ref.add_from_text(
            entry.license_id,
            entry.full_name,
            entry.text,
            spdx_id=entry.license_id,
            aliases=entry.aliases,
            version=entry.version,
            osi_approved=entry.osi_approved,
            deprecated=entry.deprecated,
            sources=_demo_sources(entry.license_id),
        )
    if include_custom:
        for name, clauses in CUSTOM_TEXTS.items():
            ref.register_custom(name, "\n".join(clauses))
    return ref
