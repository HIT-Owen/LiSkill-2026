"""License understanding model (§3.3): sentence-level term–attitude extraction."""

from .reader import (  # noqa: F401
    HeuristicLicenseReader,
    LicenseReader,
    split_clauses,
    split_sentences,
)
