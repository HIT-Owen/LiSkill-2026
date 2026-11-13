"""YAML frontmatter reader for ``SKILL.md``.

``SKILL.md`` mixes a YAML frontmatter block with a Markdown body (§2.1.2).  The
pipeline only needs the scalar keys (``name``, ``description``, ``license``,
``allowed-tools``), so a small parser is used instead of a YAML dependency —
this keeps the released demo installable with the standard library alone.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

RE_FENCE = re.compile(r"^---\s*$", re.MULTILINE)


def split_frontmatter(content: str) -> Tuple[str, str]:
    """Return ``(frontmatter, body)``; the frontmatter is empty when absent."""
    text = (content or "").lstrip("\ufeff")
    if not text.startswith("---"):
        return "", text
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if RE_FENCE.match(lines[index].strip()):
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    return "", text


def parse_frontmatter(content: str) -> Dict[str, str]:
    """Parse the flat ``key: value`` subset of YAML used by Skill manifests."""
    block, _ = split_frontmatter(content)
    data: Dict[str, str] = {}
    if not block:
        return data
    for raw in block.split("\n"):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):  # nested structure: keep the raw text
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[key] = value
    return data


def body_text(content: str) -> str:
    """The instruction body without the frontmatter block."""
    _, body = split_frontmatter(content)
    return body
