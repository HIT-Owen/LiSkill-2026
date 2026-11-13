"""The `liskill demo` end-to-end run.

Steps, each one a module call:

1. collect the sample payloads of the 17 platforms (offline) and clean them,
2. generate the calibrated synthetic ecosystem and write real skill packages,
3. run §3.2 extraction over those packages,
4. build the term database (§3.4.1),
5. detect intra-skill (§3.4.2) and inter-skill (§3.4.3) conflicts,
6. build a small license-understanding dataset (§3.3.2),
7. render `out/report.md`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ..data_collection_preprocessing.skills.runner import Collector
from ..data_collection_preprocessing.skills.sink import MemorySink
from ..extract.layers import SkillArtifact, extract_skill
from ..pipeline import LiSkillPipeline
from ..report import build_report, write_report
from ..schema import SkillLicenseDoc
from ..understand.dataset import build_dataset
from .corpus import build_synthetic_ecosystem
from .workflows import build_workflows

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples" / "skills"


@dataclass
class DemoOutcome:
    report_path: Path
    report: str
    docs: List[SkillLicenseDoc] = field(default_factory=list)
    summary: Dict[str, object] = field(default_factory=dict)


def load_example_artifacts(base: Optional[Path] = None) -> List[SkillArtifact]:
    """Load the hand-written example skills from ``examples/skills``."""
    base = Path(base or EXAMPLES_DIR)
    index_path = base / "index.json"
    if not index_path.exists():
        return []
    artifacts: List[SkillArtifact] = []
    for item in json.loads(index_path.read_text(encoding="utf-8")):
        skill_dir = base / item["dir"]
        skill_md = skill_dir / "SKILL.md"
        artifacts.append(
            SkillArtifact(
                skill_id=item["skill_id"],
                name=item["name"],
                platform=item.get("platform", "example"),
                description=item.get("description", ""),
                skill_md_content=skill_md.read_text(encoding="utf-8") if skill_md.exists() else "",
                skill_dir=skill_dir,
                repo_license=item.get("repo_license"),
            )
        )
    return artifacts


def _skill_licenses(docs: Sequence[SkillLicenseDoc]) -> Dict[str, List[str]]:
    """Node license resolution of §3.4.3 (Skill level, then Repository level)."""
    resolved: Dict[str, List[str]] = {}
    for doc in docs:
        licenses: List[str] = []
        if doc.skill is not None and doc.skill.is_usable:
            licenses = list(doc.skill.license_ids)
        elif doc.repo is not None and doc.repo.is_usable:
            licenses = list(doc.repo.license_ids)
        resolved[doc.skill_id] = licenses
    return resolved


def run_demo(
    size: int = 600,
    workflows: int = 200,
    seed: int = 20260501,
    out_dir: Optional[str | Path] = None,
    collect: bool = True,
    understanding_sample: int = 1200,
    quiet: bool = False,
    workflow_client=None,
) -> DemoOutcome:
    out = Path(out_dir or (REPO_ROOT / "out"))
    out.mkdir(parents=True, exist_ok=True)

    # 1. collection -----------------------------------------------------------
    collection_payload: Optional[Dict[str, object]] = None
    if collect:
        sink = MemorySink()
        report = Collector(sink=sink, offline=True).run()
        collection_payload = report.to_dict()

    # 2. synthetic ecosystem --------------------------------------------------
    ecosystem = build_synthetic_ecosystem(size=size, seed=seed, root=out / "skills")

    # 3. extraction -----------------------------------------------------------
    pipeline = LiSkillPipeline()
    docs = pipeline.extract(ecosystem.artifacts)
    examples = pipeline.extract(load_example_artifacts())

    # 4. term database --------------------------------------------------------
    termdb = pipeline.build_termdb()
    term_payload = {
        "licenses": len(termdb.profiles),
        "granted": sum(1 for value in termdb.grants.values() if value),
        "samples": {
            license_id: termdb.profile(license_id)
            for license_id in ("MIT", "Apache-2.0", "GPL-3.0-only", "CC-BY-NC-4.0")
            if termdb.is_known(license_id)
        },
    }

    # 5. detection ------------------------------------------------------------
    intra = pipeline.detect_intra(docs)
    if workflow_client is not None:
        # §4.4.2: requirements and activation order come from the drafting model
        from .workflows import LLMWorkflowGenerator

        catalog = [
            {"skill_id": a.skill_id, "name": a.name, "description": a.description}
            for a in ecosystem.artifacts
        ]
        chains = LLMWorkflowGenerator(workflow_client).generate(catalog, count=workflows)
    else:
        chains = build_workflows(_skill_licenses(docs), count=workflows, seed=seed + 1)
    inter = pipeline.detect_inter(chains, docs)

    # 6. understanding dataset ------------------------------------------------
    understanding_payload: Optional[Dict[str, object]] = None
    if understanding_sample:
        from ..understand.reader import HeuristicLicenseReader

        texts = {
            license_id: entry.license_text
            for license_id, entry in pipeline.reference.entries.items()
            if entry.license_text
        }
        dataset = build_dataset(
            texts,
            HeuristicLicenseReader(),
            sample_size=understanding_sample,
            seed=seed,
            out_dir=out / "understanding",
        )
        understanding_payload = {
            "candidate_sentences": dataset["candidate_sentences"],
            "deduped_sentences": dataset["deduped_sentences"],
            "annotated": dataset["annotated"],
            "splits": dataset["splits"],
        }

    # 7. report ---------------------------------------------------------------
    markdown = build_report(
        docs=docs,
        intra=intra,
        inter=inter,
        collection=collection_payload,
        term_database=term_payload,
        examples=examples,
        understanding=understanding_payload,
    )
    report_path = write_report(markdown, out / "report.md")

    if not quiet:
        print(markdown)

    summary = {
        "skills": len(docs),
        "conflicting_skills": len({c.skill_id for c in intra}),
        "workflows": len(inter),
        "conflicting_workflows": sum(1 for r in inter if r.is_conflict),
        "report": str(report_path),
    }
    return DemoOutcome(report_path=report_path, report=markdown, docs=docs, summary=summary)
