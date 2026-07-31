"""First-party vs third-party host classification.

A live capture pulls in analytics, ads, and CDN hosts alongside the target.
Flagging their CORS/headers as the *target's* risk is misleading, so every
finding is tagged relative to the capture's primary host: same registrable
domain = first-party, otherwise third-party.

Registrable domain = eTLD+1. Without bundling a full Public Suffix List we
keep a compact set of common multi-label suffixes (incl. East-African ones,
Kenya-priority) so `x.betika.com` and `betika.com` match and `foo.co.ke`
resolves to `foo.co.ke`, not `co.ke`.
"""
from __future__ import annotations

import re
from typing import Optional

PARTY_FIRST = "first_party"
PARTY_THIRD = "third_party"
PARTY_UNKNOWN = "unknown"

# Two-label public suffixes we treat as a TLD (registrable domain = label+this).
_MULTI_SUFFIX = {
    # Kenya + East Africa (project priority)
    "co.ke", "or.ke", "ne.ke", "go.ke", "ac.ke", "sc.ke", "me.ke", "mobi.ke",
    "info.ke", "co.tz", "or.tz", "co.ug", "or.ug", "co.rw",
    # UK
    "co.uk", "org.uk", "me.uk", "ac.uk", "gov.uk", "net.uk", "ltd.uk",
    # AU / NZ
    "com.au", "net.au", "org.au", "co.nz", "org.nz",
    # ZA / other Africa
    "co.za", "org.za", "com.ng", "org.ng", "com.gh",
    # Asia / America
    "co.in", "net.in", "org.in", "com.br", "com.mx", "co.jp", "or.jp",
    "com.sg", "com.hk", "com.tr",
}
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def registrable_domain(host: Optional[str]) -> str:
    """Return the eTLD+1 for a host ('' if it has none / is an IP)."""
    host = (host or "").split(":")[0].strip(".").lower()
    if not host or _IPV4.match(host) or ":" in host:  # bare host, IPv4, IPv6
        return host
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if ".".join(labels[-2:]) in _MULTI_SUFFIX:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def classify(host: Optional[str], target: Optional[str]) -> str:
    """Classify ``host`` relative to the capture's primary ``target`` host."""
    if not target:
        return PARTY_UNKNOWN
    rd_host = registrable_domain(host)
    rd_target = registrable_domain(target)
    if not rd_host or not rd_target:
        return PARTY_UNKNOWN
    return PARTY_FIRST if rd_host == rd_target else PARTY_THIRD
