"""Build the code -> meaning dictionary from correlation candidates.

Runs every strategy, groups candidates by (endpoint, path, code), and
combines agreeing evidence with the noisy-OR model. The winning meaning is
the highest-confidence single candidate; independent agreement boosts the
stored confidence. Low-confidence rows are flagged for human review.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Dict, List, Tuple

from glyph.catalog import Catalog, DictionaryEntry
from glyph.rosetta import confidence as C
from glyph.rosetta.correlate import (
    Candidate,
    dom_attribute,
    reference_join,
    sibling_pairs,
)


def _key(c: Candidate) -> Tuple:
    return (c.endpoint_id, c.json_path, json.dumps(c.code, default=str))


def collect_candidates(catalog: Catalog) -> List[Candidate]:
    """Run all correlation strategies across the catalog."""
    out: List[Candidate] = []
    for ep in catalog.endpoints():
        if ep.id is not None:
            out.extend(sibling_pairs(catalog, ep.id))
    out.extend(dom_attribute(catalog))
    out.extend(reference_join(catalog))
    return out


def build_dictionary(catalog: Catalog) -> Dict[str, int]:
    """Correlate, score, and persist the dictionary. Returns counts."""
    grouped: Dict[Tuple, List[Candidate]] = defaultdict(list)
    for cand in collect_candidates(catalog):
        grouped[_key(cand)].append(cand)

    written = 0
    review = 0
    for cands in grouped.values():
        # Pick the meaning with the strongest single supporting candidate.
        best = max(cands, key=lambda c: c.confidence)
        agreeing = [c for c in cands if c.meaning.strip().lower()
                    == best.meaning.strip().lower()]
        strategies = sorted({c.strategy for c in agreeing})
        combined = C.combine(c.confidence for c in agreeing)

        # Note any competing meanings — they lower trust and force review.
        competing = sorted({c.meaning.strip() for c in cands
                            if c.meaning.strip().lower()
                            != best.meaning.strip().lower()})
        evidence = "; ".join(dict.fromkeys(c.evidence for c in agreeing))
        if competing:
            evidence += f" | competing meanings: {', '.join(competing)}"
            combined = min(combined, 0.6)

        needs_review = combined < C.REVIEW_THRESHOLD
        catalog.upsert_dictionary(DictionaryEntry(
            endpoint_id=best.endpoint_id,
            json_path=best.json_path,
            code=best.code,
            meaning=best.meaning.strip(),
            confidence=combined,
            strategy="+".join(strategies),
            evidence=evidence,
            needs_review=needs_review,
        ))
        written += 1
        if needs_review:
            review += 1

    return {"entries": written, "needs_review": review,
            "high_confidence": written - review}
