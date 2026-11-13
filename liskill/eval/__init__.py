"""Evaluation metrics and RQ aggregation (§4.1.3, §4.2–§4.4)."""

from .metrics import (  # noqa: F401
    DetectionScore,
    PRF1,
    detection_scores,
    license_understanding_scores,
    multiset_prf1,
    term_identification_scores,
)
from .rq import (  # noqa: F401
    intra_summary,
    inter_summary,
    rq1_license_composition,
    rq1_coverage,
)
