"""Zero-rating heuristics for SNI bug-host candidates (ADR-10).

A "zero-rated" host is one a carrier lets through without deducting from a
data balance — typically because it's on a free-pack whitelist (Facebook
Free Basics, Wikipedia Zero, internet.org, operator free-fire/social packs).
These are the highest-value bug-host candidates: if the carrier zero-rates
the SNI, a TLS tunnel fronted by it rides for free.

We match against well-known global free surfaces. Operator-specific
(East-African carrier) free-pack domains rotate and are intentionally NOT
hard-coded here — the user extends ``_ZERO_RATED_PATTERNS`` as they confirm
live hits (see backlog follow-up). This is deliberately conservative: a
false "zero-rated" tag wastes the user's tunnel test, so we only tag hosts
that match a known program.
"""
from __future__ import annotations

import re
from typing import List

# Each entry: (label, compiled regex). Matched against the full lowercase
# hostname. Patterns are anchored to avoid prefix-only false positives.
_ZERO_RATED_PATTERNS: List[tuple] = [
    # --- Facebook Free Basics / Meta free surfaces ---
    ("facebook_free_basics", re.compile(r"^(?:0\.|free\.|m\.free\.|basic\.|h\.free\.)?facebook\.com$")),
    ("internet_org", re.compile(r"(^|\.)internet\.org$")),
    ("free_basics_app", re.compile(r"(^|\.)freebasics\.com$")),
    # --- Wikipedia Zero (historical; some carriers still zero-rate it) ---
    ("wikipedia_zero", re.compile(r"^(?:0\.|zero\.|m\.zero\.)wikipedia\.org$")),
    ("wikipedia_zero_m", re.compile(r"^(?:0\.|zero\.)m\.wikipedia\.org$")),
    # --- Common operator free-pack surfaces (global; carrier-rotated) ---
    ("freefire_pack", re.compile(r"(^|\.)freefire\.gmail\.com$")),
    ("opera_mini", re.compile(r"(^|\.)mini\.opera\.com$")),  # many carriers zero-rate Opera Mini
    ("whatsapp_free", re.compile(r"(^|\.)whatsapp\.net$")),  # some carriers zero-rate WhatsApp
    # --- CDN edges that are VERY commonly on free whitelists (advisory only;
    #     the carrier decides). Tagged so the user sees them surfaced, not
    #     as a definitive zero-rating. ---
    ("cloudflare_cdn_edge", re.compile(r"^[a-z0-9-]*\.?cloudflare(\-)?access?\.com$")),
]

# Hostnames whose presence is a STRONG zero-rating signal regardless of
# exact match (substring, anchored to a label boundary).
_ZERO_RATED_SUBSTRINGS = (
    ".free.", ".zero.", "freebasics", "internet.org",
    "0.facebook.com", "0.wikipedia.org",
)


def zero_rate_signals(host: str) -> List[str]:
    """Return the list of zero-rating programs ``host`` matches (possibly empty)."""
    h = (host or "").lower().strip(".")
    if not h:
        return []
    signals: List[str] = []
    for label, rx in _ZERO_RATED_PATTERNS:
        if rx.search(h):
            signals.append(label)
    # Substring signals (only if no exact-match already captured it).
    if not signals:
        for sub in _ZERO_RATED_SUBSTRINGS:
            if sub in h:
                signals.append(f"substring:{sub}")
                break
    return signals


def is_zero_rated(host: str) -> bool:
    """True if ``host`` matches any known zero-rating program."""
    return bool(zero_rate_signals(host))
