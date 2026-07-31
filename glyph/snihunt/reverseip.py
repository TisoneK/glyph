"""Reverse-IP lookup — find sibling hostnames sharing an IP (ADR-10).

The "reverse-domain" technique the user named: given an IP a captured
hostname resolved to, find every OTHER hostname that also resolves to it.
A multi-tenant host (shared IP, many hostnames) is a strong bug-host
signal — the SNI selects which site the edge serves.

Uses the public HackerTarget ``reverseiplookup`` API (no key, low-volume).
Bounded and graceful: any error or timeout returns ``[]``.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from glyph.snihunt._net import HttpGet, default_http_get, get_text

_ENDPOINT = "https://api.hackertarget.com/reverseiplookup/?q={ip}"


def reverse_ip(ip: str, http_get: Optional[HttpGet] = None,
               timeout: int = 8) -> List[str]:
    """Return the hostnames that share ``ip``, or ``[]`` on any error.

    HackerTarget's free API rate-limits after ~50 calls/day. When that
    happens it returns HTTP 200 with the body ``API count exceeded - …``
    (not an error code), so we detect it by text and return ``[]`` — the
    caller can't distinguish "genuinely 0 siblings" from "rate-limited"
    from this return value alone. See ``run_hunt``'s reverse-IP loop for
    the heuristic that surfaces a rate-limit warning.
    """
    if not ip:
        return []
    fetch = http_get or default_http_get
    text = get_text(_ENDPOINT.format(ip=ip), http_get=fetch, timeout=timeout)
    if not text:
        return []
    out: List[str] = []
    for line in text.splitlines():
        h = line.strip().lower()
        if not h or h.startswith(("api count", "error", "no dns")):
            continue
        out.append(h)
    return out


def is_rate_limited(text: str) -> bool:
    """True if a raw HackerTarget response indicates rate-limiting."""
    return bool(text) and "api count exceeded" in text.lower()
