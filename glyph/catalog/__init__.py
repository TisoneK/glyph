"""The shared catalog — the integration point for every Glyph stage."""
from __future__ import annotations

from glyph.catalog.models import (
    FINDING_RISK,
    FINDING_SENSITIVE_DATA,
    FINDING_SENSITIVE_ENDPOINT,
    FINDING_SNI_BUG_HOST,
    REACH_DIRECT,
    REACH_NEEDS_TUNNEL,
    REACH_UNREACHABLE,
    SEV_CRITICAL,
    SEV_HIGH,
    SEV_LOW,
    SEV_MEDIUM,
    DictionaryEntry,
    Endpoint,
    Finding,
    Flow,
    ObservedField,
    PageObservation,
    severity_rank,
)
from glyph.catalog.normalize import split_url, template_path
from glyph.catalog.store import (
    REVIEW_CONFIRMED,
    REVIEW_EDITED,
    REVIEW_REJECTED,
    Catalog,
)

__all__ = [
    "Catalog",
    "Endpoint",
    "Flow",
    "ObservedField",
    "DictionaryEntry",
    "PageObservation",
    "REACH_DIRECT",
    "REACH_NEEDS_TUNNEL",
    "REACH_UNREACHABLE",
    "REVIEW_CONFIRMED",
    "REVIEW_EDITED",
    "REVIEW_REJECTED",
    "Finding",
    "FINDING_SENSITIVE_DATA",
    "FINDING_SENSITIVE_ENDPOINT",
    "FINDING_RISK",
    "FINDING_SNI_BUG_HOST",
    "SEV_LOW",
    "SEV_MEDIUM",
    "SEV_HIGH",
    "SEV_CRITICAL",
    "severity_rank",
    "template_path",
    "split_url",
]
