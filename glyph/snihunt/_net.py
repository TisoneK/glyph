"""Shared network helper for the SNI hunters.

Every network hunter (dns, reverseip, ctlogs) takes a swappable
``http_get`` callable so the test suite can inject a fake and run fully
offline. The default ``http_get`` uses ``urllib.request`` with a short
timeout and a descriptive User-Agent.
"""
from __future__ import annotations

import json
from typing import Callable, Optional

UA = "glyph-recon/0.1 (+https://github.com/TisoneK/glyph)"
DEFAULT_TIMEOUT = 8

# A network fetch function: (url, timeout) -> raw bytes. Raises on any error.
HttpGet = Callable[[str, int], bytes]


def default_http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    """Fetch ``url`` and return its raw bytes. Raises on HTTP/network error."""
    import ssl
    import urllib.request
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()


def get_json(url: str, http_get: Optional[HttpGet] = None,
             timeout: int = DEFAULT_TIMEOUT):
    """Fetch ``url`` and parse JSON. Returns ``None`` on any error (callers
    degrade gracefully — a CT source being down must never break the hunt)."""
    fetch = http_get or default_http_get
    try:
        body = fetch(url, timeout)
    except Exception:
        return None
    try:
        return json.loads(body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else body)
    except (ValueError, TypeError):
        return None


def get_text(url: str, http_get: Optional[HttpGet] = None,
             timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """Fetch ``url`` as text. Returns ``None`` on any error."""
    fetch = http_get or default_http_get
    try:
        body = fetch(url, timeout)
    except Exception:
        return None
    try:
        return body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else body
    except Exception:
        return None
