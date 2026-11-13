"""Extraction and normalization (§3.2)."""

from pathlib import Path

import pytest

from liskill.extract.frontmatter import parse_frontmatter
from liskill.extract.layers import SkillArtifact, extract_skill
from liskill.extract.normalize import (
    DeclarationContext,
    DeclarationNormalizer,
    find_local_license_files,
)
from liskill.data_collection_preprocessing.licenses.reference import build_reference_set

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "skills"


@pytest.fixture(scope="module")
def normalizer() -> DeclarationNormalizer:
    return DeclarationNormalizer(build_reference_set())


def test_frontmatter_is_parsed():
    content = "---\nname: demo\ndescription: A demo skill\nlicense: MIT\n---\n\n# Demo\n"
    data = parse_frontmatter(content)
    assert data["name"] == "demo"
    assert data["license"] == "MIT"


def test_missing_frontmatter_is_tolerated():
    assert parse_frontmatter("# No frontmatter\n") == {}


@pytest.mark.parametrize(
    "declaration,kind,ids",
    [
        ("MIT", "Standard", ["MIT"]),
        ("mit license", "Standard", ["MIT"]),
        ("GPLv2", "Standard", ["GPL-2.0-only"]),
        ("Apache 2.0 / MIT", "Standard", ["Apache-2.0", "MIT"]),
        ("GPL-2.0-only AND BSD-3-Clause", "Standard", ["GPL-2.0-only", "BSD-3-Clause"]),
        ("SPDX-License-Identifier: AGPL-3.0-only", "Standard", ["AGPL-3.0-only"]),
        ("Licensed under the MIT License", "Standard", ["MIT"]),
        ("Proprietary. LICENSE.txt has complete terms", "Refer-Local", []),
        ("See the LICENSE file in the repository root", "Refer-Repo", []),
        ("No license", None, []),
    ],
)
def test_normalization_kinds(normalizer, declaration, kind, ids):
    record = normalizer.normalize(declaration, DeclarationContext()).record
    if kind is not None:
        assert record.declaration_kind == kind
    assert record.license_ids == ids


def test_custom_declaration_is_registered(normalizer):
    result = normalizer.normalize(
        "Vendor Evaluation License v3", DeclarationContext()
    )
    assert result.record.license_ids
    assert result.record.license_ids[0].startswith("LIC-")
    assert result.registered_license is not None


def test_empty_declaration_is_missing(normalizer):
    record = normalizer.normalize("", DeclarationContext()).record
    assert record.status == "Missing"
    assert record.license_ids == []


def test_local_license_file_backfills_refer_local(normalizer):
    artifact = SkillArtifact(
        skill_id="example:pdf-report",
        name="pdf-report",
        skill_md_content=(EXAMPLES / "pdf-report" / "SKILL.md").read_text(encoding="utf-8"),
        skill_dir=EXAMPLES / "pdf-report",
        repo_license=None,
    )
    doc = extract_skill(artifact, normalizer)
    assert doc.skill is not None
    assert doc.skill.license_ids and doc.skill.license_ids[0].startswith("LIC-")
    assert doc.skill.resolved_from == "local-file"


def test_three_levels_are_extracted(normalizer):
    artifact = SkillArtifact(
        skill_id="example:frontend-design",
        name="frontend-design",
        skill_md_content=(EXAMPLES / "frontend-design" / "SKILL.md").read_text(encoding="utf-8"),
        skill_dir=EXAMPLES / "frontend-design",
        repo_license="Apache-2.0",
    )
    doc = extract_skill(artifact, normalizer)
    assert doc.repo is not None and doc.repo.license_ids == ["Apache-2.0"]
    assert doc.repo.resolved_from == "github-api"
    assert doc.skill is not None and doc.skill.license_ids == ["MIT"]
    assert [c.license_ids for c in doc.components] == [["GPL-3.0-only"]]
    assert doc.components[0].file_path == "scripts/render.py"
    assert doc.status() == "Valid"


def test_component_only_skill_is_still_valid(normalizer):
    artifact = SkillArtifact(
        skill_id="example:web-scraper",
        name="web-scraper",
        skill_md_content=(EXAMPLES / "web-scraper" / "SKILL.md").read_text(encoding="utf-8"),
        skill_dir=EXAMPLES / "web-scraper",
    )
    doc = extract_skill(artifact, normalizer)
    assert doc.skill is not None and doc.skill.status == "Missing"
    assert doc.components and doc.components[0].license_ids == ["AGPL-3.0-only"]
    assert doc.status() == "Valid"


def test_local_license_files_are_found():
    names = {path.name for path in find_local_license_files(EXAMPLES / "frontend-design")}
    assert "LICENSE" in names
