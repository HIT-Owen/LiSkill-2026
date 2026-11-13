"""Declaration normalization (§3.2.2).

The pipeline turns an arbitrary license declaration into the seven
model-produced fields of Table 6:

    rule pre-filter  ->  closed-set alias match  ->  model  ->  custom registry

* **rule pre-filter**: case / hyphen / space insensitive match against
  ``license_id``, ``spdx_id`` and ``aliases``; declarations carrying a connector
  (OR / AND / "dual"), natural-language descriptions, non-English text or
  indirect references bypass it and go to the model;
* **model**: returns one JSON object restricted to the CANDIDATES set (R1/R2),
  verbatim evidence (R3) and a confidence used to route to human review;
* **indirect declarations**: ``Refer-Local`` resolved by full-text SHA-256
  against the reference set, ``Refer-Repo`` by the collected repository license;
* **custom registry**: declarations that cannot be mapped are registered as
  ``LIC-XXXX`` entries with ``source = skill-declaration``.

Without a model (offline demo) the same classification is produced by a
deterministic rule set that implements the declaration-kind definitions of the
Appendix-A prompt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ..data_collection_preprocessing.licenses.reference import ReferenceSet
from ..schema import (
    KIND_COMMERCIAL,
    KIND_CUSTOM,
    KIND_INVALID,
    KIND_PROPRIETARY,
    KIND_REFER_LOCAL,
    KIND_REFER_REPO,
    KIND_STANDARD,
    KIND_UNSPECIFIED,
    LICENSING_MULTI_AND,
    LICENSING_MULTI_OR,
    LICENSING_SINGLE,
    LEVEL_SKILL,
    RESOLVED_INLINE,
    RESOLVED_LOCAL_FILE,
    RESOLVED_REPO,
    RESOLVED_UNRESOLVED,
    STATUS_INVALID,
    STATUS_MISSING,
    STATUS_VALID,
    NormalizedRecord,
)
from .prompts import SYSTEM, build_normalization_prompt

#: names the pipeline looks for when resolving a local license document
LOCAL_LICENSE_FILES = ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCE", "COPYING", "NOTICE")

RE_OR = re.compile(r"\s*(?:\bOR\b|\bdual\b|/)\s*", re.IGNORECASE)
RE_AND = re.compile(r"\s*(?:\bAND\b|\bplus\b|&)\s*", re.IGNORECASE)
RE_CONNECTOR = re.compile(r"\b(?:OR|AND|dual|and/or)\b|/|&", re.IGNORECASE)

RE_REFER_LOCAL = re.compile(
    r"\b(?:complete|full)\s+terms\b|\bsee\s+(?:the\s+)?(?:LICEN[CS]E|COPYING|NOTICE)\b"
    r"|\b(?:LICEN[CS]E|COPYING|NOTICE)(?:\.(?:txt|md))?\s+(?:file\s+)?(?:has|contains|includes)\b"
    r"|\bin\s+(?:the\s+)?(?:LICEN[CS]E|COPYING)(?:\.(?:txt|md))?\b"
    r"|\bunder\s+the\s+terms\s+in\b",
    re.IGNORECASE,
)
RE_REFER_REPO = re.compile(
    r"\b(?:repository|repo)\b[^.]{0,40}\blicen[cs]e\b|\blicen[cs]e\b[^.]{0,40}\b(?:repository|repo)\b",
    re.IGNORECASE,
)
RE_PROPRIETARY = re.compile(
    r"\ball\s+rights\s+reserved\b|\bproprietary\b|\bconfidential\b"
    r"|\binternal\s+use\s+only\b|\bclosed[-\s]source\b|\bprivate\b",
    re.IGNORECASE,
)
RE_COMMERCIAL = re.compile(
    r"\bcommercial\s+(?:use\s+)?(?:requires?|license|licence)\b"
    r"|\bpaid\s+licen[cs]e\b|\bcontact\s+.{0,30}\bfor\s+licens",
    re.IGNORECASE,
)
RE_UNSPECIFIED = re.compile(
    r"\bopen[-\s]?source\b|\bfree\s+to\s+use\b|\bfree\s+software\b|\bMIT[- ]like\b"
    r"|\bpublic\s+domain\b|\bpermissive\b",
    re.IGNORECASE,
)
RE_INVALID = re.compile(
    r"^(?:n/?a|none|null|todo|tbd|unknown|test|placeholder|-+|\?+)$"
    r"|\b(?:my\s+project|thanks?|awesome|certified|placeholder|not\s+applicable)\b",
    re.IGNORECASE,
)
RE_NAMED_LICENSE = re.compile(
    r"\b([A-Z][\w.\-]*(?:\s+[A-Z][\w.\-]*){0,4}\s+(?:Licen[cs]e|Agreement)(?:\s+v?[\d.]+)?)\b"
)

#: component headers carry the identifier after an SPDX tag
RE_SPDX_PREFIX = re.compile(r"^\s*SPDX-License-Identifier:\s*(.+)$", re.IGNORECASE)
#: noise that may precede the license name in a natural-language note
RE_DECL_PREFIX = re.compile(
    r"^\s*(?:this\s+\w+\s+is\s+)?(?:licen[cs]ed\s+under|released\s+under|distributed\s+under"
    r"|available\s+under|under\s+the|under|the)\s+",
    re.IGNORECASE,
)


def _is_registered_custom(license_id: Optional[str]) -> bool:
    """``LIC-XXXX`` ids name the declaration's own text, not a standard license.

    Once a custom declaration has been registered, its text sits in the alias
    index, so a later identical declaration resolves by name — that must not turn
    a Proprietary/Custom declaration into a ``Standard`` one (§3.2.2).
    """
    return bool(license_id) and license_id.upper().startswith("LIC-")



@dataclass
class DeclarationContext:
    """The four-part input of Appendix A (minus the candidate set)."""

    level: str = LEVEL_SKILL
    skill_name: str = ""
    local_license_files: Sequence[str] = ()
    repo_license: str = ""
    license_texts: Dict[str, str] = field(default_factory=dict)


@dataclass
class NormalizationResult:
    record: NormalizedRecord
    #: custom license registered during this normalization, if any
    registered_license: Optional[str] = None


class DeclarationNormalizer:
    """Rule pre-filter + optional model + custom registry."""

    def __init__(self, reference: ReferenceSet, llm=None) -> None:
        self.reference = reference
        self.llm = llm

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _split_connectors(declaration: str) -> Tuple[List[str], str]:
        text = declaration.strip()
        if RE_OR.search(text):
            parts = [p for p in RE_OR.split(text) if p and p.strip()]
            if len(parts) > 1:
                return [p.strip() for p in parts], LICENSING_MULTI_OR
        if RE_AND.search(text):
            parts = [p for p in RE_AND.split(text) if p and p.strip()]
            if len(parts) > 1:
                return [p.strip() for p in parts], LICENSING_MULTI_AND
        return [text], LICENSING_SINGLE

    def _match_all(self, parts: Sequence[str]) -> Optional[List[str]]:
        ids: List[str] = []
        for part in parts:
            license_id = self.reference.match_exact(part.strip(" .;,\"'"))
            if license_id is None:
                return None
            ids.append(license_id)
        return ids

    # ------------------------------------------------------------------- public
    def normalize(
        self, declaration: Optional[str], context: Optional[DeclarationContext] = None
    ) -> NormalizationResult:
        context = context or DeclarationContext()
        raw = (declaration or "").strip()

        if not raw:
            return NormalizationResult(
                NormalizedRecord(
                    declaration_kind=KIND_UNSPECIFIED,
                    raw_declaration=None,
                    level=context.level,
                    status=STATUS_MISSING,
                    confidence=1.0,
                )
            )

        if RE_INVALID.search(raw) and len(raw) < 40:
            return NormalizationResult(
                NormalizedRecord(
                    declaration_kind=KIND_INVALID,
                    raw_declaration=raw,
                    level=context.level,
                    evidence=raw,
                    status=STATUS_INVALID,
                    confidence=0.9,
                )
            )

        # component headers arrive as "SPDX-License-Identifier: <expression>"
        expression = raw
        spdx_match = RE_SPDX_PREFIX.match(raw)
        if spdx_match:
            expression = spdx_match.group(1).strip()

        # 1. rule pre-filter — plain, connector-free declarations
        if not RE_CONNECTOR.search(expression):
            probe = RE_DECL_PREFIX.sub("", expression).rstrip(".")
            license_id = self.reference.match_exact(probe)
            if license_id is not None and not _is_registered_custom(license_id):
                return NormalizationResult(
                    NormalizedRecord(
                        license_ids=[license_id],
                        licensing_type=LICENSING_SINGLE,
                        declaration_kind=KIND_STANDARD,
                        evidence=raw,
                        confidence=0.99,
                        raw_declaration=raw,
                        level=context.level,
                        resolved_from=RESOLVED_INLINE,
                        status=STATUS_VALID,
                    )
                )

        # 2. connector-carrying declarations still resolve by alias when every
        #    part is a known identifier ("MIT OR Apache-2.0")
        parts, licensing_type = self._split_connectors(expression)
        if len(parts) > 1:
            ids = self._match_all(parts)
            if ids:
                return NormalizationResult(
                    NormalizedRecord(
                        license_ids=ids,
                        licensing_type=licensing_type,
                        declaration_kind=KIND_STANDARD,
                        evidence=raw,
                        confidence=0.97,
                        raw_declaration=raw,
                        level=context.level,
                        resolved_from=RESOLVED_INLINE,
                        status=STATUS_VALID,
                    )
                )

        # 3. model path
        kind = self._classify(raw, context)

        # 3b. a license name buried in a longer sentence ("Licensed under the MIT
        #     License, see LICENSE") still counts as a Standard declaration
        if kind in (KIND_UNSPECIFIED, KIND_CUSTOM) and len(expression.split()) <= 12:
            license_id = self.reference.guess_by_name(expression)
            if license_id is not None and not _is_registered_custom(license_id):
                return NormalizationResult(
                    NormalizedRecord(
                        license_ids=[license_id],
                        licensing_type=LICENSING_SINGLE,
                        declaration_kind=KIND_STANDARD,
                        evidence=raw,
                        confidence=0.9,
                        raw_declaration=raw,
                        level=context.level,
                        resolved_from=RESOLVED_INLINE,
                        status=STATUS_VALID,
                    )
                )

        if self.llm is not None:
            record = self._ask_model(raw, context)
            if record is not None:
                record.raw_declaration = raw
                record.level = context.level
                return NormalizationResult(record)

        # 4. deterministic fallback (offline)
        return self._heuristic(raw, context, kind, expression)

    # --------------------------------------------------------------- classifier
    def _classify(self, raw: str, context: DeclarationContext) -> str:
        if RE_REFER_REPO.search(raw):
            return KIND_REFER_REPO
        if RE_REFER_LOCAL.search(raw):
            return KIND_REFER_LOCAL
        if RE_PROPRIETARY.search(raw):
            return KIND_PROPRIETARY
        if RE_COMMERCIAL.search(raw):
            return KIND_COMMERCIAL
        if RE_UNSPECIFIED.search(raw):
            return KIND_UNSPECIFIED
        if RE_NAMED_LICENSE.search(raw):
            return KIND_CUSTOM
        if context.repo_license and len(raw.split()) <= 3:
            return KIND_REFER_REPO
        return KIND_UNSPECIFIED

    def _heuristic(
        self,
        raw: str,
        context: DeclarationContext,
        kind: str,
        declaration: Optional[str] = None,
    ) -> NormalizationResult:
        """Deterministic fallback.

        ``declaration`` is the prefix-stripped text (a component header arrives as
        ``SPDX-License-Identifier: <text>``), so the same unmappable declaration is
        registered as one custom license instead of one per carrier level.  The
        record still keeps ``raw`` as its evidence and raw declaration (§3.2.1).
        """
        label = (declaration or raw).strip() or raw
        record = NormalizedRecord(
            declaration_kind=kind,
            evidence=raw,
            confidence=0.7,
            raw_declaration=raw,
            level=context.level,
        )
        if kind == KIND_REFER_LOCAL:
            record.target_hint = self._target_hint(raw) or (
                list(context.local_license_files)[0] if context.local_license_files else "LICENSE"
            )
            record.resolved_from = RESOLVED_UNRESOLVED
            record.status = STATUS_MISSING
        elif kind == KIND_REFER_REPO:
            record.target_hint = "LICENSE"
            record.resolved_from = RESOLVED_REPO if context.repo_license else RESOLVED_UNRESOLVED
            record.status = STATUS_MISSING
        elif kind in (KIND_PROPRIETARY, KIND_COMMERCIAL, KIND_CUSTOM):
            entry = self.reference.register_custom(label, context.license_texts.get(raw, ""))
            record.license_ids = [entry.license_id]
            record.resolved_from = RESOLVED_INLINE
            record.status = STATUS_VALID
            record.confidence = 0.75
            return NormalizationResult(record, registered_license=entry.license_id)
        else:  # Unspecified
            record.resolved_from = RESOLVED_UNRESOLVED
            record.status = STATUS_MISSING
        return NormalizationResult(record)

    @staticmethod
    def _target_hint(raw: str) -> Optional[str]:
        match = re.search(
            r"\b(LICEN[CS]E(?:\.(?:txt|md))?|COPYING|NOTICE)\b", raw, re.IGNORECASE
        )
        return match.group(1) if match else None

    # ------------------------------------------------------------------ model IO
    def _ask_model(self, raw: str, context: DeclarationContext) -> Optional[NormalizedRecord]:
        prompt = build_normalization_prompt(
            raw,
            self.reference.candidates,
            level=context.level,
            skill_name=context.skill_name,
            local_license_files=context.local_license_files,
            repo_license=context.repo_license,
        )
        try:
            answer = self.llm.complete(prompt, json_mode=True, system=SYSTEM)
        except Exception:  # pragma: no cover - network path
            return None
        return self.parse_model_answer(answer, raw, context)

    def parse_model_answer(
        self, answer: str, raw: str, context: DeclarationContext
    ) -> Optional[NormalizedRecord]:
        text = (answer or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

        # R1 / R2: identifiers must come from the closed candidate set
        allowed = set(self.reference.candidates)
        ids = [str(i) for i in data.get("license_ids") or [] if str(i) in allowed]
        kind = str(data.get("declaration_kind") or KIND_UNSPECIFIED)
        if kind not in {
            KIND_STANDARD, KIND_CUSTOM, KIND_PROPRIETARY, KIND_COMMERCIAL,
            KIND_REFER_LOCAL, KIND_REFER_REPO, KIND_UNSPECIFIED, KIND_INVALID,
        }:
            kind = KIND_UNSPECIFIED
        licensing_type = str(data.get("licensing_type") or LICENSING_SINGLE)
        if licensing_type not in {LICENSING_SINGLE, LICENSING_MULTI_OR, LICENSING_MULTI_AND}:
            licensing_type = LICENSING_SINGLE
        evidence = str(data.get("evidence") or "")
        if evidence and evidence not in raw:  # R3
            evidence = raw

        record = NormalizedRecord(
            license_ids=ids,
            licensing_type=licensing_type,
            declaration_kind=kind,
            exceptions=[str(e) for e in data.get("exceptions") or []],
            target_hint=data.get("target_hint"),
            evidence=evidence,
            confidence=float(data.get("confidence") or 0.5),
            raw_declaration=raw,
            level=context.level,
            resolved_from=RESOLVED_INLINE if ids else RESOLVED_UNRESOLVED,
            status=STATUS_VALID if ids else STATUS_MISSING,
        )
        if kind == KIND_INVALID:
            record.status = STATUS_INVALID
        return record

    # ------------------------------------------------- indirect declaration fill
    def resolve_refer_local(
        self, record: NormalizedRecord, skill_dir: Optional[Path]
    ) -> Optional[str]:
        """Backfill a ``Refer-Local`` record: full-text hash first, then names.

        When the pointed-to document matches no reference text (§3.2.2), its
        terms are still available — the declaration is registered as a custom
        license instead of being dropped.
        """
        if skill_dir is None or record.declaration_kind != KIND_REFER_LOCAL:
            return None
        first_text = ""
        for path in find_local_license_files(Path(skill_dir)):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            first_text = first_text or text
            license_id = self.reference.match_text(text)
            if license_id is None:
                license_id = self.reference.guess_by_name(text[:512])
            if license_id:
                record.license_ids = [license_id]
                record.status = STATUS_VALID
                record.resolved_from = RESOLVED_LOCAL_FILE
                record.evidence = text.strip().splitlines()[0][:200] if text.strip() else path.name
                return license_id
        if first_text.strip():
            entry = self.reference.register_custom(
                record.raw_declaration or record.target_hint or "custom", first_text
            )
            record.license_ids = [entry.license_id]
            record.declaration_kind = KIND_CUSTOM
            record.status = STATUS_VALID
            record.resolved_from = RESOLVED_LOCAL_FILE
            record.evidence = first_text.strip().splitlines()[0][:200]
            return entry.license_id
        record.status = STATUS_MISSING
        record.resolved_from = RESOLVED_UNRESOLVED
        return None

    def resolve_refer_repo(
        self, record: NormalizedRecord, repo_license: str
    ) -> Optional[str]:
        """Backfill a ``Refer-Repo`` record from the collected repository license."""
        if record.declaration_kind != KIND_REFER_REPO:
            return None
        license_id = self.reference.match_exact(repo_license) if repo_license else None
        if license_id:
            record.license_ids = [license_id]
            record.status = STATUS_VALID
            record.resolved_from = RESOLVED_REPO
            return license_id
        record.status = STATUS_MISSING
        record.resolved_from = RESOLVED_UNRESOLVED
        return None


def find_local_license_files(skill_dir: Path) -> List[Path]:
    """Recursively look for license documents inside a skill package."""
    if not skill_dir.exists():
        return []
    wanted = {name.lower() for name in LOCAL_LICENSE_FILES}
    found: List[Path] = []
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file() and path.name.lower() in wanted:
            found.append(path)
    return found
