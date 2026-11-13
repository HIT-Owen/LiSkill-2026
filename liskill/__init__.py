"""LiSkill — term-level license conflict detection for Agent Skill ecosystems.

The package mirrors the four modules of the paper (§3.1–§3.4):

    data_collection_preprocessing
                skill harvesting, preprocessing and the licence reference set
    extract     licence extraction + normalization (Repository / Skill / Component)
    understand  sentence-level term–attitude license understanding model
    conflict    term database, LST (intra-skill) and SCC (inter-skill) detection

Everything is importable and runnable with the standard library only; heavier
backends (MongoDB, Qwen3.5-9B LoRA) are optional and lazily imported.
"""

__version__ = "0.1.0"

from .ontology import ATTITUDES, TERMS, TERM_BY_ID, TERM_BY_NAME, Term  # noqa: F401

__all__ = ["__version__", "ATTITUDES", "TERMS", "TERM_BY_ID", "TERM_BY_NAME", "Term"]
