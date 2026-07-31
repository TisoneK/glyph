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

from glyph.snihunt._net import HttpGet, get_text

_ENDPOINT = "https://api.hackertarget.com/reverseiplookup/?q={ip}"


def reverse_ip(ip: str, http_get: Optional[HttpGet] = None,
               timeout: int = 8) -> List[str]:
    """Return the hostnames that share ``ip``, or ``[]`` on any error."""
    if not ip:
        return []
    fetch = http_get or (lambda u, t: __import__("glyph.snihunt._net", fromlist=["default_http_get"]).default_http_get(u, t))
    text = get_text(_ENDPOINT.format(ip=ip), http_get=fetch, timeout=timeout)
    if not text:
        return []
    # HackerTarget returns a newline-separated list of hostnames (no JSON).
    # An error message starts with "API count exceeded" or "error" — drop those.
    out: List[str] = []
    for line in text.splitlines():
        h = line.strip().lower()
        if not h or h.startswith(("api count", "error", "no dns")):
            continue
        out.append(h)
    return out
