"""DNS-over-HTTPS resolution for the SNI hunt (ADR-10).

Uses Google (``dns.google``) and Cloudflare (``cloudflare-dns.com``) DoH
endpoints — both public, both JSON. Resolves A + AAAA records. Cached per
host for the lifetime of a hunt so a repeat candidate is a dict lookup, not
a second network round-trip. Falls back to the system resolver
(``socket.getaddrinfo``) if both DoH providers fail.
"""
from __future__ import annotations

import socket
from typing import Callable, Dict, List, Optional

from glyph.snihunt._net import HttpGet, default_http_get, get_json

# Both providers return the same RFC 8484-ish JSON shape; query one, fall
# back to the other. Order matters: dns.google tends to be more lenient on
# the accept header.
_PROVIDERS = (
    "https://dns.google/resolve?name={name}&type={type}",
    "https://cloudflare-dns.com/dns-query?name={name}&type={type}",
)
# DNS record type numbers (DoH uses the IANA type code for `type=`).
_TYPE_A = 1
_TYPE_AAAA = 28


def _doh(name: str, rtype: int, http_get: Callable[[str, int], bytes]) -> List[str]:
    """Query both DoH providers for ``name``/``rtype`` and return the answers."""
    out: List[str] = []
    for tmpl in _PROVIDERS:
        url = tmpl.format(name=name, type=rtype)
        data = get_json(url, http_get=http_get)
        if not data or data.get("Status") != 0:
            continue
        for ans in data.get("Answer") or []:
            # type matches rtype; data is the IP for A/AAAA records.
            if ans.get("type") == rtype and ans.get("data"):
                out.append(str(ans["data"]))
        if out:
            break  # first provider that answered wins
    return out


def resolve(host: str, http_get: Optional[HttpGet] = None,
            cache: Optional[Dict[str, List[str]]] = None) -> List[str]:
    """Resolve ``host`` to a list of IP strings (A + AAAA). Empty on failure.

    ``cache`` lets the hunt share one resolution map across candidates; if
    passed, results are stored and reused.
    """
    # IPs don't need resolving; hostnames that are already IPs pass through.
    import ipaddress
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass

    if cache is not None and host in cache:
        return cache[host]

    fetch = http_get or default_http_get
    ips: List[str] = []
    try:
        ips += _doh(host, _TYPE_A, fetch)
        ips += _doh(host, _TYPE_AAAA, fetch)
    except Exception:
        ips = []

    # System-resolver fallback if DoH was unreachable.
    if not ips:
        try:
            for fam, _, _, _, sockaddr in socket.getaddrinfo(
                    host, None, proto=socket.IPPROTO_TCP):
                ip = sockaddr[0]
                if ip and ip not in ips:
                    ips.append(ip)
        except socket.gaierror:
            ips = []

    # Dedup, preserve order.
    seen = set()
    dedup: List[str] = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            dedup.append(ip)
    if cache is not None:
        cache[host] = dedup
    return dedup
