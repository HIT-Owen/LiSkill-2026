"""Synthetic LiSkill-mini ecosystem used by the released demo.

The real study annotates 2,027,275 raw records down to 825,784 unique skills
(§3.1.1).  Those artifacts are not redistributable, so the demo generates a
*small, calibrated* stand-in:

* platform mix follows Table 3,
* declaration coverage follows Table 9 (89.25% missing / 0.15% invalid /
  10.59% valid),
* the standard-license mix follows Table 10,
* the cross-level license-pair mix follows the pairs reported in §4.4.1,
* each generated skill is written to disk as a real package (``SKILL.md``,
  ``LICENSE``, ``scripts/*.py``), so the extraction pipeline in
  :mod:`liskill.extract` runs end to end instead of reading a fixture table.

The output is a demo corpus — every report marks it as DEMO.  Do not read its
numbers as the measurements of the paper.
"""

from __future__ import annotations

import hashlib
import random
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ..schema import SkillRecord
from ..extract.layers import SkillArtifact

#: Table 3 — raw records per platform
PLATFORM_COUNTS: Dict[str, int] = {
    "clawhub": 82477,
    "agentskills.in": 199396,
    "skills.lc": 320111,
    "skillsmp": 272177,
    "skills.rest": 223433,
    "skills.sh": 90625,
    "skillmaps": 11258,
    "smithery": 66604,
    "agent-skills.md": 73579,
    "agnxi": 11654,
    "awesome-agent-skills": 40818,
    "toprankskills": 118474,
    "lobehub": 274494,
    "skills.palebluedot": 70985,
    "skillsdirectory": 34044,
    "skillsmk": 14896,
    "skillszoo": 122250,
}

#: Table 10 — share of the valid standard declarations
STANDARD_LICENSE_MIX: List[Tuple[str, float]] = [
    ("MIT", 75.21),
    ("Apache-2.0", 15.13),
    ("MIT-0", 0.96),
    ("AGPL-3.0-only", 0.82),
    ("BSD-3-Clause", 0.72),
    ("GPL-3.0-only", 0.45),
    ("CC0-1.0", 0.35),
    ("CC-BY-4.0", 0.28),
    ("CC-BY-SA-4.0", 0.21),
    ("SUL-1.0", 0.14),
    ("GPL-2.0-only", 0.12),
    ("MPL-2.0", 0.10),
    ("BSD-2-Clause", 0.09),
    ("LGPL-2.1-only", 0.08),
    ("ISC", 0.07),
    ("Elastic-2.0", 0.06),
    ("BUSL-1.1", 0.05),
    ("CC-BY-NC-4.0", 0.05),
    ("CC-BY-NC-SA-4.0", 0.04),
    ("SSPL-1.0", 0.03),
    ("Unlicense", 0.02),
    ("Zlib", 0.02),
]

#: Table 15 — (repository/parent, component/child, weight) of cross-level pairs
INTRA_CONFLICT_PAIRS: List[Tuple[str, str, float]] = [
    ("MIT", "AGPL-3.0-only", 18.42),
    ("MIT", "GPL-3.0-only", 12.75),
    ("Apache-2.0", "GPL-3.0-only", 8.53),
    ("MIT", "GPL-2.0-only", 7.21),
    ("MIT", "<custom>", 6.84),
    ("Apache-2.0", "<custom>", 4.51),
    ("MIT", "CC-BY-NC-SA-4.0", 4.12),
    ("Apache-2.0", "Elastic-2.0", 3.93),
    ("MIT", "CC-BY-NC-4.0", 3.24),
    ("MIT", "BUSL-1.1", 2.81),
]

#: custom declarations seen in the ecosystem (§4.2)
CUSTOM_DECLARATIONS: List[str] = [
    "Proprietary. LICENSE.txt has complete terms",
    "Internal use only - AdaptiveX brand assets",
    "Vendor Evaluation License v3",
    "All rights reserved",
    "Internal use only",
]

PLATFORM_WEIGHTED: List[str] = []
for _platform, _count in PLATFORM_COUNTS.items():
    PLATFORM_WEIGHTED.extend([_platform] * max(1, round(_count / 12_000)))

TOPICS = [
    ("frontend-design", "Generate production-ready frontend components from a design brief"),
    ("pdf-report", "Render a structured data set into a paginated PDF report with charts"),
    ("data-connector", "Connect to an SQL warehouse, run a query and return structured rows"),
    ("web-scraper", "Fetch a page, extract the article body and return it as Markdown"),
    ("changelog-writer", "Summarise merged pull requests into a release changelog"),
    ("k8s-deploy", "Deploy a container image to a Kubernetes cluster and verify rollouts"),
    ("seo-audit", "Audit a web page for SEO issues and suggest fixes"),
    ("unit-test-gen", "Generate unit tests for untested Python functions"),
    ("image-optimizer", "Compress and convert images into modern web formats"),
    ("slack-notifier", "Send structured notifications to a Slack channel"),
    ("invoice-parser", "Extract line items from a PDF invoice into structured JSON"),
    ("video-transcriber", "Transcribe an audio file and produce a timestamped transcript"),
    ("csv-cleaner", "Normalise a messy CSV file into a tidy table"),
    ("prompt-linter", "Lint an LLM prompt for ambiguity and unsafe instructions"),
    ("api-mocker", "Generate a mock server from an OpenAPI specification"),
    ("skill-auditor", "Review a skill package for missing metadata and unsafe scripts"),
]

REPO_LICENSE_MIX: List[str] = ["MIT", "Apache-2.0", "MIT", "MIT", "Apache-2.0", "GPL-3.0-only", "AGPL-3.0-only"]


@dataclass
class SyntheticEcosystem:
    """The generated demo dataset: records plus on-disk packages."""

    records: List[SkillRecord] = field(default_factory=list)
    artifacts: List[SkillArtifact] = field(default_factory=list)
    root: Optional[Path] = None
    #: skill_id -> (repo_license, skill_license, [component licenses])
    ground_truth: Dict[str, Tuple[Optional[str], Optional[str], List[str]]] = field(
        default_factory=dict
    )

    def __len__(self) -> int:
        return len(self.records)

    def cleanup(self) -> None:
        if self.root is not None and self.root.exists():
            import shutil

            shutil.rmtree(self.root, ignore_errors=True)


def _weighted_choice(rng: random.Random, items: Sequence[Tuple[str, float]]) -> str:
    total = sum(weight for _, weight in items)
    pick = rng.uniform(0, total)
    upto = 0.0
    for value, weight in items:
        upto += weight
        if pick <= upto:
            return value
    return items[-1][0]


def _skill_id(platform: str, name: str, suffix: str) -> str:
    """SHA-256(name + description) as in §3.1.1 (here: name + suffix)."""
    digest = hashlib.sha256(f"{name}{suffix}".encode("utf-8")).hexdigest()
    return f"{platform}:{digest[:16]}"


def _skill_md(name: str, description: str, license_value: Optional[str]) -> str:
    lines = ["---", f"name: {name}", f"description: {description}"]
    if license_value is not None:
        lines.append(f"license: {license_value}")
    lines += ["allowed-tools: Read, Write, Bash", "---", "", f"# {name.replace('-', ' ').title()}", ""]
    lines += [
        "## Workflow",
        "",
        "1. Read the task input.",
        "2. Run the bundled script.",
        "3. Return the structured result.",
        "",
        "## Boundaries",
        "",
        "- Never touch files outside the workspace.",
        "- Ask for confirmation before a destructive action.",
        "",
    ]
    return "\n".join(lines)


def _component_script(index: int, license_header: Optional[str]) -> str:
    header = f"# SPDX-License-Identifier: {license_header}\n" if license_header else ""
    return (
        f"{header}# Copyright (c) 2026 Example Author\n"
        f'"""Helper module {index}."""\n\n\n'
        f"def run(payload):\n"
        f'    """Process the payload and return the result."""\n'
        f"    return payload\n"
    )


def build_synthetic_ecosystem(
    size: int = 600,
    seed: int = 20260501,
    root: Optional[Path] = None,
    write_packages: bool = True,
) -> SyntheticEcosystem:
    """Generate ``size`` skills with the paper's reported distributions."""
    rng = random.Random(seed)
    ecosystem = SyntheticEcosystem()
    ecosystem.root = Path(root) if root else Path(tempfile.mkdtemp(prefix="liskill-demo-"))

    for index in range(size):
        topic_name, topic_desc = TOPICS[index % len(TOPICS)]
        platform = rng.choice(PLATFORM_WEIGHTED)
        suffix = f"-{index:05d}"
        name = f"{topic_name}{suffix}" if index >= len(TOPICS) else topic_name
        description = f"{topic_desc} (#{index})"
        skill_id = _skill_id(platform, name, suffix)

        roll = rng.random()
        repo_license: Optional[str] = None
        skill_license: Optional[str] = None
        component_licenses: List[str] = []

        if roll < 0.8925:  # Table 9 — Missing
            pass
        elif roll < 0.8940:  # Table 9 — Invalid
            skill_license = rng.choice(["TODO", "n/a", "placeholder"])
        else:  # Table 9 — Valid
            if rng.random() < 0.049:  # 4.90% custom declarations
                skill_license = rng.choice(CUSTOM_DECLARATIONS)
            else:
                skill_license = _weighted_choice(rng, STANDARD_LICENSE_MIX)
                # the repository default is usually the same, sometimes different
                if rng.random() < 0.72:
                    repo_license = skill_license
                else:
                    repo_license = rng.choice(REPO_LICENSE_MIX)

            if rng.random() < 0.512:  # calibrated so 5.42% of *all* skills conflict
                pair_key = _weighted_choice(
                    rng, [(f"{p}|{c}", w) for p, c, w in INTRA_CONFLICT_PAIRS]
                )
                parent, child = pair_key.split("|")
                if child == "<custom>":
                    child = rng.choice(CUSTOM_DECLARATIONS)
                component_licenses = [child]
                if repo_license is None:
                    repo_license = parent
            elif rng.random() < 0.35:  # a consistent component declaration
                component_licenses = [skill_license]

        skill_dir = ecosystem.root / f"{platform}" / name
        skill_md = _skill_md(name, description, skill_license)
        if write_packages:
            (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
            header = component_licenses[0] if component_licenses else None
            (skill_dir / "scripts" / "run.py").write_text(
                _component_script(index, header), encoding="utf-8"
            )
            if skill_license and skill_license in _STANDARD_IDS:
                (skill_dir / "LICENSE").write_text(
                    f"{skill_license} license text\n", encoding="utf-8"
                )
            elif skill_license and "LICENSE.txt" in (skill_license or ""):
                (skill_dir / "LICENSE.txt").write_text(
                    "Example Corp — Proprietary Skill License\n\n"
                    "All rights reserved.\n\n"
                    "You may not copy, modify, distribute, sublicense, or reverse engineer "
                    "this software without the prior written permission of the copyright "
                    "holder.\n\nCommercial use requires a separate paid license agreement.\n",
                    encoding="utf-8",
                )

        record = SkillRecord(
            skill_id=skill_id,
            platform=platform,
            name=name,
            description=description,
            author=f"author-{index % 97}",
            skill_md_content=skill_md,
            repo_license=repo_license,
            repo_url=f"https://github.com/example/{name}",
            repo_full_name=f"example/{name}",
            default_branch="main",
            relative_path=name,
            insert_data_time=1_750_000_000 + index,
        )
        ecosystem.records.append(record)
        ecosystem.artifacts.append(
            SkillArtifact(
                skill_id=skill_id,
                name=name,
                platform=platform,
                description=description,
                skill_md_content=skill_md,
                skill_dir=skill_dir if write_packages else None,
                repo_license=repo_license,
            )
        )
        ecosystem.ground_truth[skill_id] = (repo_license, skill_license, component_licenses)

    return ecosystem


_STANDARD_IDS = {
    "MIT", "MIT-0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib",
    "Unlicense", "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-NC-4.0",
    "CC-BY-NC-SA-4.0", "GPL-2.0-only", "GPL-3.0-only", "AGPL-3.0-only",
    "LGPL-2.1-only", "MPL-2.0", "Elastic-2.0", "BUSL-1.1", "SSPL-1.0", "SUL-1.0",
}


def build_raw_records(size: int = 2400, seed: int = 7) -> List[dict]:
    """Generate the *raw* multi-platform records used to demo the cleaning stage.

    Every skill appears on one to three platforms with the same name and
    description, so the SHA-256 + earliest-timestamp rule of §3.1.1 has
    something to collapse.
    """
    rng = random.Random(seed)
    raw: List[dict] = []
    for index in range(size):
        topic_name, topic_desc = TOPICS[index % len(TOPICS)]
        name = f"{topic_name}" if index < len(TOPICS) else f"{topic_name}-{index}"
        description = f"{topic_desc} (#{index})"
        replicas = rng.choice([1, 1, 2, 2, 3])
        platforms = rng.sample(list(PLATFORM_COUNTS), replicas)
        for order, platform in enumerate(platforms):
            body = "## Workflow\n\n1. Read\n2. Run\n3. Return\n"
            if rng.random() < 0.03:  # too short to be a real skill
                body = "TODO\n"
            raw.append(
                {
                    "platform": platform,
                    "name": name,
                    "description": description if rng.random() > 0.02 else "",
                    "author": f"author-{index % 97}",
                    "skill_md_content": f"---\nname: {name}\ndescription: {description}\n---\n\n{body}",
                    "repo_url": f"https://github.com/example/{name}",
                    "collected_at": 1_750_000_000 + index * 10 + order,
                }
            )
    return raw
