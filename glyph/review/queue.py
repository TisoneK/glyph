"""Human-in-the-loop review queue over Rosetta's dictionary.

Rosetta narrows; the human confirms (RESEARCH.md §10). These helpers wrap
the catalog's review persistence so the CLI (and scripts) can walk the
low-confidence rows and record a decision on each: confirm the proposed
meaning, edit it, or reject the mapping outright. Decisions are ground
truth — a later ``glyph rosetta`` re-run never overwrites them.
"""
from __future__ import annotations

from typing import Dict, List

from glyph.catalog import (
    REVIEW_CONFIRMED,
    REVIEW_EDITED,
    REVIEW_REJECTED,
    Catalog,
    DictionaryEntry,
)


def pending(catalog: Catalog) -> List[DictionaryEntry]:
    """Rows still awaiting a human decision (flagged, not yet reviewed)."""
    return catalog.dictionary(needs_review=True, review_state="unreviewed")


def confirm(catalog: Catalog, entry_id: int) -> bool:
    """Accept the proposed meaning as correct."""
    return catalog.review_entry(entry_id, REVIEW_CONFIRMED)


def edit(catalog: Catalog, entry_id: int, meaning: str) -> bool:
    """Accept the mapping but replace the meaning with a corrected one."""
    if not meaning:
        raise ValueError("edited meaning must be non-empty")
    return catalog.review_entry(entry_id, REVIEW_EDITED, meaning=meaning)


def reject(catalog: Catalog, entry_id: int) -> bool:
    """Mark the mapping wrong — it drops out of dictionary output."""
    return catalog.review_entry(entry_id, REVIEW_REJECTED)


def auto_confirm(catalog: Catalog, threshold: float) -> int:
    """Confirm every pending row whose confidence is >= ``threshold``.

    A convenience for triage: trust the model above a bar, review the rest
    by hand. Returns the number confirmed.
    """
    n = 0
    for entry in pending(catalog):
        if entry.confidence >= threshold and entry.id is not None:
            confirm(catalog, entry.id)
            n += 1
    return n


def stats(catalog: Catalog) -> Dict[str, int]:
    """Counts of dictionary rows by review state (for progress display)."""
    all_rows = catalog.dictionary(include_rejected=True)
    out = {"total": len(all_rows), "pending": 0, "confirmed": 0,
           "edited": 0, "rejected": 0, "unreviewed": 0}
    for e in all_rows:
        if e.review_state == REVIEW_CONFIRMED:
            out["confirmed"] += 1
        elif e.review_state == REVIEW_EDITED:
            out["edited"] += 1
        elif e.review_state == REVIEW_REJECTED:
            out["rejected"] += 1
        else:
            out["unreviewed"] += 1
            if e.needs_review:
                out["pending"] += 1
    return out
