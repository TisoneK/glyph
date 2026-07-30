"""Gating profile — rate-limiting and bot-management signals per host.

Detects rate-limit headers and 429s, and recognises the fingerprints of
common bot-management vendors from response headers/cookies. This is
observation, not evasion: Glyph documents what defends a surface
(RESEARCH.md §10) — legal review precedes any bypass work.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List

from glyph.catalog import Catalog

# Response header / cookie substring -> bot-management vendor.
_BOT_SIGNS = {
    "cf-ray": "Cloudflare",
    "cf-mitigated": "Cloudflare",
    "__cf_bm": "Cloudflare Bot Management",
    "cf-chl": "Cloudflare Challenge",
    "x-datadome": "DataDome",
    "datadome": "DataDome",
    "_px": "PerimeterX/HUMAN",
    "px-": "PerimeterX/HUMAN",
    "ak_bmsc": "Akamai Bot Manager",
    "bm_sz": "Akamai Bot Manager",
    "x-akamai": "Akamai",
    "incap_ses": "Imperva/Incapsula",
    "visid_incap": "Imperva/Incapsula",
    "x-kasada": "Kasada",
    "kpsdk": "Kasada",
    "x-arkose": "Arkose Labs",
}
_RATE_HEADERS = ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining",
                 "x-ratelimit-reset", "ratelimit-limit", "ratelimit-remaining",
                 "x-rate-limit-limit")


def profile(catalog: Catalog) -> Dict[str, Dict[str, Any]]:
    """Return ``{host: {rate_limited, rate_limit_headers, bot_management, evidence}}``."""
    acc: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"rate_limited": False, "rate_limit_headers": set(),
                 "bot_management": set(), "evidence": [], "statuses": set()})

    for flow in catalog.all_flows():
        rec = acc[flow.host]
        headers = {k.lower(): v for k, v in (flow.resp_headers or {}).items()}
        blob = " ".join(headers.keys()) + " " + " ".join(
            str(v).lower() for v in headers.values())

        if flow.status == 429:
            rec["rate_limited"] = True
            rec["statuses"].add(429)
            rec["evidence"].append("HTTP 429 observed")
        for h in _RATE_HEADERS:
            if h in headers:
                rec["rate_limit_headers"].add(h)
                rec["rate_limited"] = True
        for needle, vendor in _BOT_SIGNS.items():
            if needle in blob:
                rec["bot_management"].add(vendor)
                rec["evidence"].append(f"{needle} -> {vendor}")

    out: Dict[str, Dict[str, Any]] = {}
    for host, rec in acc.items():
        out[host] = {
            "rate_limited": rec["rate_limited"],
            "rate_limit_headers": sorted(rec["rate_limit_headers"]),
            "bot_management": sorted(rec["bot_management"]),
            "evidence": list(dict.fromkeys(rec["evidence"])),
        }
    return out
