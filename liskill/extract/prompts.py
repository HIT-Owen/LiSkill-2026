"""Prompt of Appendix A — declaration normalization.

The input has four parts, exactly as described in §3.2.2:

1. ``declaration`` — the raw declaration string,
2. context — level, skill name, ``local_license_files``, ``repo_license``,
3. ``CANDIDATES`` — the closed set of SPDX identifiers,
4. nine examples covering every ``declaration_kind``.

The output is a fixed JSON object with the seven model-produced fields of
Table 6.
"""

from __future__ import annotations

import json
from typing import Iterable, Sequence

SYSTEM = """You are an expert in open-source license compliance. You read a license
declaration extracted from an Agent Skill artifact and return one JSON object.
Return JSON only. Do not output explanations, markdown fences, or comments.

### DECLARATION KINDS (choose exactly one)
Standard     The declaration names one or more licenses listed in CANDIDATES,
             possibly with different casing, spacing, hyphenation or version
             notation, or with a trailing "License" / "Licence".
Custom       The declaration explicitly names a license that is NOT in
             CANDIDATES (e.g. a vendor- or project-specific license).
Proprietary  The declaration states that all rights are reserved, or that the
             artifact is private / internal, without naming any license.
Commercial   The declaration states that commercial use requires a separate
             paid license, without naming any license.
Refer-Local  The declaration does not name a license but points to a license
             document inside the Skill package
             (e.g. "complete terms in LICENSE.txt").
Refer-Repo   The declaration does not name a license but points to a license
             document in the associated repository
             (e.g. "see LICENSE in repository").
Unspecified  The declaration expresses an intention to be open source or free
             to use, without naming any license.
Invalid      The declaration is unrelated to licensing (jokes, project names,
             professional certifications, placeholders).

### LICENSING TYPES (choose exactly one)
Single     One license applies, or no license is identified.
Multi-OR   The identified licenses are alternatives ("OR", "/", "dual").
Multi-AND  All identified licenses apply simultaneously ("AND", "subject to").

### RULES
R1. Every element of "license_ids" MUST be copied verbatim from CANDIDATES.
R2. Never invent an identifier that is not in CANDIDATES.
R3. "evidence" MUST be a verbatim substring of the declaration.
R4. "target_hint" is filled only for Refer-Local and Refer-Repo.
R5. "confidence" is a number in [0, 1]; use < 0.6 when the declaration is
    ambiguous.
R6. "exceptions" lists additional restrictions attached to a standard license
    (e.g. "Commons Clause"); it is [] otherwise.
R7. When the declaration is empty, return Unspecified with empty license_ids.
"""

EXAMPLES = [
    {
        "declaration": "MIT",
        "context": {"level": "Skill", "local_license_files": ["LICENSE"], "repo_license": "MIT"},
        "answer": {
            "license_ids": ["MIT"], "licensing_type": "Single",
            "declaration_kind": "Standard", "exceptions": [],
            "target_hint": None, "evidence": "MIT", "confidence": 0.99,
        },
    },
    {
        "declaration": "Apache 2.0 / MIT",
        "context": {"level": "Skill", "local_license_files": [], "repo_license": None},
        "answer": {
            "license_ids": ["Apache-2.0", "MIT"], "licensing_type": "Multi-OR",
            "declaration_kind": "Standard", "exceptions": [],
            "target_hint": None, "evidence": "Apache 2.0 / MIT", "confidence": 0.95,
        },
    },
    {
        "declaration": "GPL-2.0-only AND BSD-3-Clause",
        "context": {"level": "Component", "local_license_files": [], "repo_license": None},
        "answer": {
            "license_ids": ["GPL-2.0-only", "BSD-3-Clause"], "licensing_type": "Multi-AND",
            "declaration_kind": "Standard", "exceptions": [],
            "target_hint": None, "evidence": "GPL-2.0-only AND BSD-3-Clause", "confidence": 0.95,
        },
    },
    {
        "declaration": "MIT with Commons Clause",
        "context": {"level": "Skill", "local_license_files": [], "repo_license": "MIT"},
        "answer": {
            "license_ids": ["MIT"], "licensing_type": "Single",
            "declaration_kind": "Standard", "exceptions": ["Commons Clause"],
            "target_hint": None, "evidence": "MIT with Commons Clause", "confidence": 0.9,
        },
    },
    {
        "declaration": "Proprietary. LICENSE.txt has complete terms",
        "context": {"level": "Skill", "local_license_files": ["LICENSE.txt"], "repo_license": None},
        "answer": {
            "license_ids": [], "licensing_type": "Single",
            "declaration_kind": "Refer-Local", "exceptions": [],
            "target_hint": "LICENSE.txt",
            "evidence": "LICENSE.txt has complete terms", "confidence": 0.85,
        },
    },
    {
        "declaration": "See the LICENSE file in the repository root.",
        "context": {"level": "Skill", "local_license_files": [], "repo_license": "Apache-2.0"},
        "answer": {
            "license_ids": [], "licensing_type": "Single",
            "declaration_kind": "Refer-Repo", "exceptions": [],
            "target_hint": "LICENSE", "evidence": "See the LICENSE file", "confidence": 0.8,
        },
    },
    {
        "declaration": "Vendor Evaluation License v3",
        "context": {"level": "Skill", "local_license_files": [], "repo_license": None},
        "answer": {
            "license_ids": [], "licensing_type": "Single",
            "declaration_kind": "Custom", "exceptions": [],
            "target_hint": None, "evidence": "Vendor Evaluation License v3", "confidence": 0.7,
        },
    },
    {
        "declaration": "Internal use only",
        "context": {"level": "Skill", "local_license_files": [], "repo_license": None},
        "answer": {
            "license_ids": [], "licensing_type": "Single",
            "declaration_kind": "Proprietary", "exceptions": [],
            "target_hint": None, "evidence": "Internal use only", "confidence": 0.8,
        },
    },
    {
        "declaration": "Licensed under CC BY-NC 4.0 for non-commercial use",
        "context": {"level": "Skill", "local_license_files": [], "repo_license": None},
        "answer": {
            "license_ids": ["CC-BY-NC-4.0"], "licensing_type": "Single",
            "declaration_kind": "Standard", "exceptions": [],
            "target_hint": None,
            "evidence": "CC BY-NC 4.0 for non-commercial use", "confidence": 0.9,
        },
    },
]


def build_normalization_prompt(
    declaration: str,
    candidates: Sequence[str],
    level: str = "Skill",
    skill_name: str = "",
    local_license_files: Iterable[str] = (),
    repo_license: str = "",
) -> str:
    """Render the Appendix-A user prompt."""
    example_block = "\n".join(
        f'  {index + 1}. {json.dumps(item, ensure_ascii=False)}'
        for index, item in enumerate(EXAMPLES)
    )
    return f"""### DECLARATION
{declaration or "<empty>"}

### CONTEXT
level: {level}
skill_name: {skill_name}
local_license_files: {list(local_license_files)}
repo_license: {repo_license or "<none>"}

### CANDIDATES
{json.dumps(list(candidates), ensure_ascii=False)}

### EXAMPLES
{example_block}

### OUTPUT
Return one JSON object with keys:
license_ids, licensing_type, declaration_kind, exceptions, target_hint,
evidence, confidence.
"""
