"""Three-level license declaration extraction (§3.2.1, §3.2.2 instance extraction).

    Repository level  the repository-wide license collected with the record
                      (``repo_license``, GitHub API) — no model involved
    Skill level       the ``license`` field of the ``SKILL.md`` frontmatter, and,
                      when that field is missing or only points elsewhere, the
                      ``LICENSE`` / ``LICENSE.txt`` / ``LICENSE.md`` / ``COPYING``
                      / ``NOTICE`` files at the skill root
    Component level   the head comment of every file under ``scripts/``,
                      ``references/`` and ``assets/`` — ``SPDX-License-Identifier``
                      lines, copyright blocks and natural-language license notes

Every extracted declaration keeps its physical location and the verbatim
evidence, so a record can always be traced back to a file (or to "absent").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..schema import (
    LEVEL_COMPONENT,
    LEVEL_REPOSITORY,
    LEVEL_SKILL,
    RESOLVED_GITHUB_API,
    RESOLVED_INLINE,
    RESOLVED_UNRESOLVED,
    STATUS_MISSING,
    NormalizedRecord,
    SkillLicenseDoc,
)
from .frontmatter import parse_frontmatter
from .normalize import (
    DeclarationContext,
    DeclarationNormalizer,
    find_local_license_files,
)

#: file types scanned at the component level (§3.2.2)
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".sh", ".bash", ".zsh", ".rb", ".pl",
    ".php", ".java", ".kt", ".go", ".rs", ".c", ".h", ".cc", ".cpp", ".cs",
    ".sql", ".md", ".markdown", ".txt", ".yml", ".yaml", ".toml", ".json",
    ".html", ".css", ".scss", ".vue", ".swift", ".lua", ".r", ".m", ".jl",
}
#: component scan budget (§3.2.2: skip binaries and files above 1 MB)
MAX_COMPONENT_BYTES = 1_000_000
HEAD_LINES = 20

RE_SPDX = re.compile(
    r"SPDX-License-Identifier:\s*([A-Za-z0-9.\-+ ]+)", re.IGNORECASE
)
RE_COPYRIGHT = re.compile(r"(?:copyright|\(c\)|©)\s*(?:\(c\))?\s*\d{4}", re.IGNORECASE)
RE_LICENSE_NOTE = re.compile(
    r"\b(?:licen[cs]ed\s+under|released\s+under|distributed\s+under|under\s+the\s+"
    r"(?:terms|MIT|Apache|BSD|GPL|LGPL|AGPL|MPL|ISC|CC)|this\s+(?:file|script)\s+is\s+"
    r"(?:part\s+of|licen[cs]ed))\b[^\n]{0,120}",
    re.IGNORECASE,
)


@dataclass
class SkillArtifact:
    """One skill as it exists on disk plus the metadata collected with it."""

    skill_id: str
    name: str = ""
    platform: str = ""
    description: str = ""
    skill_md_content: str = ""
    skill_dir: Optional[Path] = None
    repo_license: Optional[str] = None
    repo_root: Optional[Path] = None

    def local_license_files(self) -> List[str]:
        if self.skill_dir is None:
            return []
        return [p.name for p in find_local_license_files(Path(self.skill_dir))]


# --------------------------------------------------------------------------- #
# Repository level
# --------------------------------------------------------------------------- #
def extract_repository_level(
    artifact: SkillArtifact, normalizer: DeclarationNormalizer
) -> NormalizedRecord:
    """Repository level: the license collected from the GitHub API."""
    declaration = (artifact.repo_license or "").strip()
    if not declaration:
        # a LICENSE file in the downloaded repository archive can fill the gap
        if artifact.repo_root is not None:
            for path in find_local_license_files(Path(artifact.repo_root)):
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                license_id = normalizer.reference.match_text(text)
                if license_id:
                    return NormalizedRecord(
                        license_ids=[license_id],
                        declaration_kind="Standard",
                        evidence=path.name,
                        confidence=0.99,
                        raw_declaration=path.name,
                        level=LEVEL_REPOSITORY,
                        resolved_from="local-file",
                        status="Valid",
                    )
        return NormalizedRecord(
            declaration_kind="Unspecified",
            level=LEVEL_REPOSITORY,
            status=STATUS_MISSING,
            resolved_from=RESOLVED_UNRESOLVED,
        )

    license_id = normalizer.reference.match_exact(declaration)
    if license_id:
        return NormalizedRecord(
            license_ids=[license_id],
            declaration_kind="Standard",
            evidence=declaration,
            confidence=0.99,
            raw_declaration=declaration,
            level=LEVEL_REPOSITORY,
            resolved_from=RESOLVED_GITHUB_API,
            status="Valid",
        )
    result = normalizer.normalize(
        declaration, DeclarationContext(level=LEVEL_REPOSITORY, skill_name=artifact.name)
    )
    record = result.record
    record.level = LEVEL_REPOSITORY
    record.resolved_from = record.resolved_from or RESOLVED_GITHUB_API
    return record


# --------------------------------------------------------------------------- #
# Skill level
# --------------------------------------------------------------------------- #
def extract_skill_level(
    artifact: SkillArtifact, normalizer: DeclarationNormalizer
) -> NormalizedRecord:
    """Skill level: ``SKILL.md`` frontmatter, else the root license documents."""
    content = artifact.skill_md_content
    if not content and artifact.skill_dir is not None:
        skill_md = Path(artifact.skill_dir) / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding="utf-8", errors="ignore")
    metadata = parse_frontmatter(content)
    declaration = (metadata.get("license") or metadata.get("licence") or "").strip()

    context = DeclarationContext(
        level=LEVEL_SKILL,
        skill_name=artifact.name or metadata.get("name", ""),
        local_license_files=artifact.local_license_files(),
        repo_license=artifact.repo_license or "",
    )

    if declaration:
        record = normalizer.normalize(declaration, context).record
        record.level = LEVEL_SKILL
        if record.declaration_kind in ("Refer-Local", "Refer-Repo"):
            normalizer.resolve_refer_local(record, artifact.skill_dir)
            if not record.license_ids:
                normalizer.resolve_refer_repo(record, artifact.repo_license or "")
        return record

    # no frontmatter field: fall back to a license document at the skill root
    for path in find_local_license_files(Path(artifact.skill_dir)) if artifact.skill_dir else []:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        license_id = normalizer.reference.match_text(text) or normalizer.reference.guess_by_name(
            text[:512]
        )
        if license_id:
            return NormalizedRecord(
                license_ids=[license_id],
                declaration_kind="Standard",
                evidence=text.strip().splitlines()[0][:200],
                confidence=0.95,
                raw_declaration=text.strip()[:200],
                level=LEVEL_SKILL,
                resolved_from="local-file",
                status="Valid",
            )
        result = normalizer.normalize(text.strip()[:400], context)
        record = result.record
        record.level = LEVEL_SKILL
        record.resolved_from = "local-file"
        if record.license_ids:
            record.status = "Valid"
        return record

    return NormalizedRecord(
        declaration_kind="Unspecified",
        level=LEVEL_SKILL,
        status=STATUS_MISSING,
        resolved_from=RESOLVED_UNRESOLVED,
    )


# --------------------------------------------------------------------------- #
# Component level
# --------------------------------------------------------------------------- #
def _iter_text_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if path.name.lower() in {"license", "license.txt", "license.md", "copying", "notice"}:
            continue
        try:
            if path.stat().st_size > MAX_COMPONENT_BYTES:
                continue
        except OSError:
            continue
        yield path


def extract_components(
    artifact: SkillArtifact, normalizer: DeclarationNormalizer
) -> List[NormalizedRecord]:
    """Component level: head comments of the files inside the skill package."""
    if artifact.skill_dir is None or not Path(artifact.skill_dir).exists():
        return []
    root = Path(artifact.skill_dir)
    records: List[NormalizedRecord] = []

    for path in _iter_text_files(root):
        try:
            head = "".join(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(True)[:HEAD_LINES]
            )
        except OSError:
            continue
        if not head.strip():
            continue

        relative = str(path.relative_to(root)).replace("\\", "/")
        declaration = _declaration_from_head(head)
        if declaration is None:
            continue

        context = DeclarationContext(
            level=LEVEL_COMPONENT,
            skill_name=artifact.name,
            local_license_files=artifact.local_license_files(),
            repo_license=artifact.repo_license or "",
        )
        result = normalizer.normalize(declaration, context)
        record = result.record
        record.level = LEVEL_COMPONENT
        record.file_path = relative
        record.raw_declaration = declaration
        if record.resolved_from is None:
            record.resolved_from = RESOLVED_INLINE
        records.append(record)
    return records


def _declaration_from_head(head: str) -> Optional[str]:
    """Pick the license declaration out of a file head comment."""
    spdx = RE_SPDX.search(head)
    if spdx:
        return f"SPDX-License-Identifier: {spdx.group(1).strip()}"
    note = RE_LICENSE_NOTE.search(head)
    if note:
        return note.group(0).strip()
    if RE_COPYRIGHT.search(head):
        # a bare copyright block is not a license declaration
        return None
    return None


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
def extract_skill(
    artifact: SkillArtifact, normalizer: DeclarationNormalizer
) -> SkillLicenseDoc:
    """Produce the per-skill license document of §3.2.3."""
    doc = SkillLicenseDoc(skill_id=artifact.skill_id)
    doc.repo = extract_repository_level(artifact, normalizer)
    doc.skill = extract_skill_level(artifact, normalizer)
    doc.components = extract_components(artifact, normalizer)
    return doc


def extract_skills(
    artifacts: Iterable[SkillArtifact], normalizer: DeclarationNormalizer
) -> List[SkillLicenseDoc]:
    return [extract_skill(artifact, normalizer) for artifact in artifacts]


def artifact_from_record(record, skill_dir: Optional[Path] = None) -> SkillArtifact:
    """Adapter from a Table-4 record to the on-disk artifact description."""
    return SkillArtifact(
        skill_id=record.skill_id,
        name=record.name,
        platform=record.platform,
        description=record.description,
        skill_md_content=record.skill_md_content,
        skill_dir=skill_dir,
        repo_license=record.repo_license,
    )
