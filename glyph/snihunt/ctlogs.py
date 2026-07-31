"""Certificate-Transparency subdomain enumeration (ADR-10).

For a registrable domain, query CT logs for every hostname that has EVER
held a TLS cert. The user explicitly wants NEW hosts (not published
bughost.txt lists), and CT logs are the canonical fresh source — they
record every cert issued, including for subdomains that no longer resolve
but may still be cached zero-rated by a carrier.

Primary source: certspotter (free, JSON, no key for low volume).
Fallback: crt.sh (JSON output, often slow/overloaded — kept as a secondary).
Both are bounded with a per-domain cap and 429-aware.
"""
from __future__ import annotations

from typing import Callable, Optional, Set

from glyph.snihunt._net import HttpGet, get_json, get_text

_CERTSPOTTER = "https://api.certspotter.com/v1/issuances?domain={domain}&include_subdomains=true&expand=dns_names"
_CRTSH = "https://crt.sh/?q=%.{domain}&output=json"

# Cap per domain so a giant CT result set (e.g. cloudflare.com itself)
# doesn't dominate the hunt. 500 distinct subdomains is plenty to surface
# candidates.
_MAX_PER_DOMAIN = 500


def _normalize(name: str) -> str:
    return (name or "").strip().lower().strip(".")


def _within(parent: str, name: str) -> bool:
    """True if ``name`` is ``parent`` or a subdomain of it (CT sometimes
    returns unrelated SANs that shared a cert)."""
    if not name or not parent:
        return False
    return name == parent or name.endswith("." + parent)


def _from_certspotter(domain: str, fetch: HttpGet) -> Set[str]:
    data = get_json(_CERTSPOTTER.format(domain=domain), http_get=fetch)
    if not isinstance(data, list):
        return set()
    out: Set[str] = set()
    for entry in data:
        # With expand=dns_names, each entry carries the cert's SAN list.
        for n in entry.get("dns_names") or []:
            n = _normalize(n)
            if _within(domain, n):
                out.add(n)
        if len(out) >= _MAX_PER_DOMAIN:
            break
    return out


def _from_crtsh(domain: str, fetch: HttpGet) -> Set[str]:
    data = get_json(_CRTSH.format(domain=domain), http_get=fetch)
    if not isinstance(data, list):
        return set()
    out: Set[str] = set()
    for entry in data:
        for key in ("name_value", "name_values"):
            val = entry.get(key)
            if not val:
                continue
            if isinstance(val, list):
                names = val
            else:
                names = str(val).splitlines()
            for n in names:
                n = _normalize(n)
                if _within(domain, n):
                    out.add(n)
        if len(out) >= _MAX_PER_DOMAIN:
            break
    return out


def subdomains(domain: str, http_get: Optional[HttpGet] = None) -> Set[str]:
    """Return the set of subdomains of ``domain`` that have held a cert.

    Tries certspotter first, falls back to crt.sh. Returns whatever it
    gathered (possibly empty) — never raises.
    """
    if not domain:
        return set()
    from glyph.snihunt._net import default_http_get
    fetch = http_get or default_http_get
    try:
        out = _from_certspotter(domain, fetch)
        if out:
            return out
    except Exception:
        out = set()
    try:
        out |= _from_crtsh(domain, fetch)
    except Exception:
        pass
    return out


def has_wildcard(subdomains: Set[str], domain: str) -> bool:
    """True if the CT result set includes a wildcard cert entry (``*.domain``)."""
    return any(s.startswith("*.") for s in subdomains) or f"*.{domain}" in subdomains
