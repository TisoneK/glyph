"""Confidence model for Rosetta mappings.

Each correlation strategy carries a base confidence. When two independent
strategies agree on the same code -> meaning, the combined confidence is
boosted (noisy-OR): agreement is strong evidence. Anything below
:data:`REVIEW_THRESHOLD` is queued for human confirmation — Rosetta
narrows the work, it does not remove judgement (RESEARCH.md §10).
"""
from __future__ import annotations

from typing import Iterable

# Base confidence per strategy.
SIBLING_PREFIX = 0.97   # status + status_label in the same object
SIBLING_GENERIC = 0.90  # {code, label} / {type, name} in the same object
DOM_ATTR_MATCH = 0.95   # <span data-status=3>Shipped</span>, attr name matches field
DOM_ATTR_GENERIC = 0.75  # code value in some DOM attribute, name doesn't match
REFERENCE_HINTED = 0.85  # user_id -> users object's name
REFERENCE_BARE = 0.60   # id value matches an object, no name-path hint

REVIEW_THRESHOLD = 0.90


def combine(confidences: Iterable[float]) -> float:
    """Noisy-OR combination: agreement raises confidence, never past ~1.

    ``combine([0.9]) == 0.9``; ``combine([0.9, 0.75])`` > 0.9.
    """
    product_complement = 1.0
    for c in confidences:
        c = max(0.0, min(1.0, c))
        product_complement *= (1.0 - c)
    return round(1.0 - product_complement, 4)
