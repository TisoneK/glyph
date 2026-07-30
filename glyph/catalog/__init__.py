"""The shared catalog — the integration point for every Glyph stage."""
from __future__ import annotations

from glyph.catalog.models import (
    REACH_DIRECT,
    REACH_NEEDS_TUNNEL,
    REACH_UNREACHABLE,
    DictionaryEntry,
    Endpoint,
    Flow,
    ObservedField,
    PageObservation,
)
from glyph.catalog.normalize import split_url, template_path
from glyph.catalog.store import Catalog

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
    "template_path",
    "split_url",
]
