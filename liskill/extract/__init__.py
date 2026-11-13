"""License extraction and normalization (§3.2)."""

from .frontmatter import parse_frontmatter  # noqa: F401
from .layers import SkillArtifact, extract_components, extract_skill  # noqa: F401
from .normalize import DeclarationNormalizer  # noqa: F401
