"""Agent workflows for the Inter-skill demo (§4.4.2).

An agent's real planning trace cannot be observed, so — as the paper does —
workflows come from task requirements: a requirement drives a recall over skill
names/descriptions and the minimal set of skills is emitted in activation order.

Two implementations of that procedure live here:

:class:`LLMWorkflowGenerator`
    the paper's path (§4.4.2).  DeepSeek-V4-Flash-0731 writes one realistic
    request per functional category, then picks the minimal skill set and its
    activation order.  Requirements that need a single skill produce no call edge
    and are dropped, exactly as §4.4.2 states.

:func:`build_workflows`
    the offline stand-in used by ``liskill demo`` and the tests.  It follows the
    same requirement → recall → minimal-set shape but samples deterministically
    instead of calling a model, and it calibrates the conflicting-pair rate to
    §4.4.2 so the demo report stays comparable.  It is *not* the model-driven
    generator and the report marks the whole run **DEMO**.
"""

from __future__ import annotations

import json
import random
import re
from typing import Dict, List, Optional, Sequence, Tuple

from ..conflict.scc import SkillCompositionChain
from .corpus import TOPICS

#: Table 17 — conflicting license pairs of dynamic composition (unordered)
INTER_CONFLICT_PAIRS: List[tuple] = [
    ("MIT", "<custom>", 16.52),
    ("Apache-2.0", "<custom>", 14.23),
    ("GPL-3.0-only", "Apache-2.0", 11.81),
    ("AGPL-3.0-only", "<custom>", 8.44),
    ("GPL-3.0-only", "<custom>", 6.95),
    ("AGPL-3.0-only", "Apache-2.0", 5.82),
    ("CC-BY-SA-4.0", "GPL-2.0-only", 4.93),
    ("CC-BY-NC-SA-4.0", "MIT", 4.21),
    ("GPL-2.0-only", "Apache-2.0", 3.72),
    ("GPL-3.0-only", "Elastic-2.0", 3.63),
]

REQUIREMENTS: List[str] = [
    "Analyse last quarter's sales data and deliver a PDF report to the management team",
    "Refresh the marketing site: generate new components, optimise the images and check SEO",
    "Transcribe the customer call, summarise it and notify the account owner",
    "Clean the raw export, load it into the warehouse and generate the monthly changelog",
    "Audit an existing skill package for missing metadata and unsafe scripts",
    "Build a mock backend from the OpenAPI spec and deploy it to staging",
    "Turn the design brief into a component library and publish the release notes",
    "Parse the invoices from the shared inbox and reconcile them with the ledger",
]


def _pick_weighted(rng: random.Random, items: Sequence[tuple]) -> tuple:
    total = sum(weight for *_, weight in items)
    pick = rng.uniform(0, total)
    upto = 0.0
    for item in items:
        upto += item[-1]
        if pick <= upto:
            return item
    return items[-1]


def build_workflows(
    skill_licenses: Dict[str, Sequence[str]],
    count: int = 200,
    seed: int = 20260502,
    conflict_rate: float = 0.076,
) -> List[SkillCompositionChain]:
    """Generate ``count`` activation chains over the given skills.

    ``skill_licenses`` maps ``skill_id -> license ids`` (Skill level first, then
    Repository level) and is used to pick chains that reproduce the conflict
    rate; the detector itself never sees this hint.
    """
    rng = random.Random(seed)
    by_license: Dict[str, List[str]] = {}
    for skill_id, licenses in skill_licenses.items():
        if licenses:
            by_license.setdefault(licenses[0], []).append(skill_id)
    # the recall only ever returns skills that carry a usable declaration
    pool = sorted(skill_id for ids in by_license.values() for skill_id in ids)
    by_family: Dict[str, List[str]] = {}
    for skill_id in pool:
        by_family.setdefault(license_family(skill_licenses[skill_id][0]), []).append(skill_id)

    chains: List[SkillCompositionChain] = []
    for index in range(count):
        length = rng.choice([2, 2, 3, 3, 4])
        requirement = REQUIREMENTS[index % len(REQUIREMENTS)]
        skill_ids: List[str] = []

        if rng.random() < conflict_rate:
            # retry until a pair the pool can actually instantiate is found,
            # otherwise the injected conflict silently degrades into a clean chain
            for _ in range(8):
                left, right, _ = _pick_weighted(rng, INTER_CONFLICT_PAIRS)
                first = _find_skill(rng, by_license, left)
                second = _find_skill(rng, by_license, right)
                if first and second and first != second:
                    skill_ids.extend([first, second])
                    rng.shuffle(skill_ids)
                    break
        else:
            # an agent composes skills of one stack: the remaining members come
            # from the same license family as the seed skill
            seed_skill = rng.choice(pool)
            family = license_family(skill_licenses[seed_skill][0])
            candidates = by_family.get(family) or pool
            skill_ids.append(seed_skill)
            for _ in range(length - 1):
                skill_ids.append(rng.choice(candidates))

        for _ in range(length - len(skill_ids)):
            anchor = skill_ids[0] if skill_ids else rng.choice(pool)
            family = license_family(skill_licenses[anchor][0])
            candidates = by_family.get(family) or pool
            skill_ids.insert(rng.randrange(len(skill_ids) + 1), rng.choice(candidates))

        # de-duplicate while keeping the activation order
        seen: List[str] = []
        for skill_id in skill_ids:
            if skill_id and skill_id not in seen:
                seen.append(skill_id)
        if len(seen) < 2:
            continue
        chains.append(
            SkillCompositionChain(
                workflow_id=f"wf-{index:04d}",
                skill_ids=seen,
                description=requirement,
            )
        )
    return chains


def _find_skill(
    rng: random.Random,
    by_license: Dict[str, List[str]],
    license_id: str,
) -> Optional[str]:
    """Pick a skill carrying ``license_id``; ``"<custom>"`` matches any LIC-XXXX."""
    if license_id == "<custom>":
        custom = [
            skill_id
            for lic, ids in by_license.items()
            if lic.startswith("LIC-")
            for skill_id in ids
        ]
        return rng.choice(custom) if custom else None
    candidates = by_license.get(license_id)
    return rng.choice(candidates) if candidates else None


def requirement_categories() -> List[str]:
    """The 16 functional categories behind the requirement generation."""
    return [name for name, _ in TOPICS]


# --------------------------------------------------------------------------- #
# model-driven generation (§4.4.2)
# --------------------------------------------------------------------------- #
REQUIREMENT_PROMPT = """You plan tasks for an AI agent that activates Agent Skills.

Category: {category}

Write {per_category} realistic requests a user would ask such an agent to carry
out by activating SEVERAL skills of this category one after another. Name
concrete artefacts (files, systems, teams) the way real users do.
Reply with JSON only: {{"requirements": ["...", ...]}}"""

COMPOSITION_PROMPT = """Task: {requirement}

Candidate skills:
{candidates}

Select the MINIMAL set of candidates that together complete the task and order
them by activation: the first is invoked first, the last produces the final
artefact. Omit anything you do not need and do not invent skills.
Reply with JSON only: {{"skills": ["<skill_id>", ...]}}"""

_TOKENS = re.compile(r"[a-z0-9]{3,}")


def _json_object(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_requirements(raw: str) -> List[str]:
    return [str(item).strip() for item in _json_object(raw).get("requirements", []) if str(item).strip()]


def parse_skill_order(raw: str, allowed: Sequence[str]) -> List[str]:
    """Activation order of the model answer, restricted to the recalled candidates."""
    allowed_set = set(allowed)
    items = _json_object(raw).get("skills", [])
    order: List[str] = []
    for item in items if isinstance(items, list) else []:
        skill_id = str(item).strip()
        if skill_id in allowed_set and skill_id not in order:
            order.append(skill_id)
    return order


def recall_skills(requirement: str, catalog: Sequence[Dict[str, str]], top_k: int = 24) -> List[Dict[str, str]]:
    """The recall step of §4.4.2: requirement text against skill name/description."""
    want = set(_TOKENS.findall(requirement.lower()))
    scored: List[Tuple[float, Dict[str, str]]] = []
    for entry in catalog:
        have = set(_TOKENS.findall(f"{entry.get('name', '')} {entry.get('description', '')}".lower()))
        score = len(want & have) / (1 + len(have) ** 0.5)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda pair: -pair[0])
    return [entry for _, entry in scored[:top_k]]


class LLMWorkflowGenerator:
    """§4.4.2: DeepSeek-V4-Flash-0731 writes the requirements and composes the chains.

    ``per_category`` is sized so that 16 categories cover the 500 workflows the
    paper keeps; a requirement that yields a single skill produces no call edge
    and is discarded, which is why the returned count can be smaller than asked.
    """

    def __init__(
        self,
        client,
        categories: Optional[Sequence[str]] = None,
        recall_size: int = 24,
    ) -> None:
        self.client = client
        self.categories = list(categories or requirement_categories())
        self.recall_size = recall_size

    def generate_requirements(self, per_category: int = 32) -> List[Tuple[str, str]]:
        pairs: List[Tuple[str, str]] = []
        for category in self.categories:
            raw = self.client.complete(
                REQUIREMENT_PROMPT.format(category=category, per_category=per_category),
                json_mode=True,
            )
            pairs.extend((category, text) for text in parse_requirements(raw))
        return pairs

    def compose(self, requirement: str, catalog: Sequence[Dict[str, str]]) -> List[str]:
        candidates = recall_skills(requirement, catalog, self.recall_size)
        if len(candidates) < 2:
            return []
        listing = "\n".join(
            f"- {entry['skill_id']}: {entry.get('name', '')} — "
            f"{(entry.get('description') or '')[:160]}"
            for entry in candidates
        )
        raw = self.client.complete(
            COMPOSITION_PROMPT.format(requirement=requirement, candidates=listing),
            json_mode=True,
        )
        return parse_skill_order(raw, [entry["skill_id"] for entry in candidates])

    def generate(
        self,
        catalog: Sequence[Dict[str, str]],
        count: int = 500,
        per_category: int = 32,
    ) -> List[SkillCompositionChain]:
        chains: List[SkillCompositionChain] = []
        for _category, requirement in self.generate_requirements(per_category):
            order = self.compose(requirement, catalog)
            if len(order) < 2:  # no call edge -> outside the §4.4.2 evaluation set
                continue
            chains.append(
                SkillCompositionChain(
                    workflow_id=f"wf-{len(chains):04d}",
                    skill_ids=order,
                    description=requirement,
                )
            )
            if len(chains) >= count:
                break
        return chains



PERMISSIVE = {
    "MIT", "MIT-0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "Zlib", "Unlicense", "CC0-1.0", "CC-BY-4.0",
}
WEAK_COPYLEFT = {"LGPL-2.1-only", "MPL-2.0", "CC-BY-SA-4.0"}
STRONG_COPYLEFT = {"GPL-2.0-only", "GPL-3.0-only", "AGPL-3.0-only", "SSPL-1.0"}
RESTRICTED = {
    "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "Elastic-2.0", "BUSL-1.1", "SUL-1.0",
}


def license_family(license_id: str) -> str:
    """Coarse license family, used to keep generated stacks self-consistent."""
    if not license_id:
        return "unknown"
    if license_id.startswith("LIC-"):
        return "custom"
    if license_id in PERMISSIVE:
        return "permissive"
    if license_id in WEAK_COPYLEFT:
        return "weak-copyleft"
    if license_id in STRONG_COPYLEFT:
        return "strong-copyleft"
    if license_id in RESTRICTED:
        return "restricted"
    return "other"
