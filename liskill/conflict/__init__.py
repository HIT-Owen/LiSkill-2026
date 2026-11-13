"""Unified term-level conflict detection (§3.4)."""

from .matrix import (  # noqa: F401
    COMPATIBILITY_MATRIX,
    TermConflict,
    conditions_compatible,
    edge_conflicts,
    lookup,
)
from .termdb import TermDatabase  # noqa: F401
from .lst import IntraConflict, build_lst, detect_intra  # noqa: F401
from .scc import InterConflict, SkillCompositionChain, detect_inter  # noqa: F401
