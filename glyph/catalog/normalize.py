"""Path normalization — collapse concrete URLs onto endpoint templates.

``/users/123/orders/8ac2`` -> ``/users/{id}/orders/{hash}`` so that many
flows aggregate onto one :class:`~glyph.catalog.models.Endpoint`. The
heuristics are deliberately conservative and domain-neutral.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                   r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_HEX = re.compile(r"^[0-9a-fA-F]{16,}$")
_INT = re.compile(r"^\d+$")
_MIXED_ID = re.compile(r"^(?=.*\d)[A-Za-z0-9_\-]{8,}$")
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

# Two-label public suffixes treated as a TLD, so ``foo.co.ke`` -> ``foo.co.ke``
# (not ``co.ke``) and ``x.betika.com`` / ``betika.com`` share a domain. A
# compact set (incl. East-African, Kenya-priority) rather than a full PSL.
_MULTI_SUFFIX = {
    "co.ke", "or.ke", "ne.ke", "go.ke", "ac.ke", "sc.ke", "me.ke", "mobi.ke",
    "info.ke", "co.tz", "or.tz", "co.ug", "or.ug", "co.rw",
    "co.uk", "org.uk", "me.uk", "ac.uk", "gov.uk", "net.uk", "ltd.uk",
    "com.au", "net.au", "org.au", "co.nz", "org.nz",
    "co.za", "org.za", "com.ng", "org.ng", "com.gh",
    "co.in", "net.in", "org.in", "com.br", "com.mx", "co.jp", "or.jp",
    "com.sg", "com.hk", "com.tr",
}


def registrable_domain(host):
    """Return the eTLD+1 for a host ('' if none / an IP). Domain-neutral."""
    host = (host or "").split(":")[0].strip(".").lower()
    if not host or _IPV4.match(host) or ":" in host:
        return host
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if ".".join(labels[-2:]) in _MULTI_SUFFIX:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _placeholder(segment: str) -> str:
    """Return the template placeholder for one path segment, or the segment."""
    if _INT.match(segment):
        return "{id}"
    if _UUID.match(segment):
        return "{uuid}"
    if _HEX.match(segment):
        return "{hash}"
    if _MIXED_ID.match(segment) and not segment.isalpha():
        # long, contains a digit, not a plain word (e.g. "8ac2f", "v2token")
        return "{id}"
    return segment


def template_path(path: str) -> str:
    """Collapse a concrete path to its endpoint template."""
    if not path:
        return "/"
    parts = path.split("/")
    return "/".join(_placeholder(p) if p else p for p in parts)


def split_url(url: str):
    """Return ``(host, path, query_dict)`` for a URL.

    ``host`` includes a non-default port. ``query_dict`` maps each key to a
    scalar (last value) so it round-trips cleanly through JSON storage.
    """
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    query = {k: (v[-1] if v else "") for k, v in parse_qs(parts.query).items()}
    return host, parts.path or "/", query
