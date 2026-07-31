"""CDN / frontable-edge detection (ADR-10).

A host that resolves to a CDN edge IP is "frontable" — the TLS SNI can be
set to one hostname while the actual tunneled destination is another host
served by the same edge. This is the "cloudflare" technique the user named.

Four CDNs are detected:
  - Cloudflare (AS13335) — by IP range only (IPv4 + IPv6). NO suffix
    detector: Cloudflare doesn't own a *.cloudflare.com edge suffix the way
    Akamai owns *.akamai.net; frontable Cloudflare hosts are CUSTOMER
    domains that resolve to Cloudflare IPs. So Cloudflare detection REQUIRES
    a resolved/captured IP — the online path (DoH) catches it; the offline
    path (--no-net, no captured IP) MISSES Cloudflare-fronted hosts.
  - Fastly (AS54113) — by IP range + suffix (*.fastly.net, *.fastlylb.net).
  - CloudFront (AS16509) — by IP range + suffix (*.cloudfront.net).
  - Akamai (AS20940) — by suffix only (no IP range; Akamai's rotates).

Net: offline detection covers Fastly/CloudFront/Akamai via suffix; Cloudflare
needs the online path. This is a known limitation, not a bug — there is no
safe Cloudflare suffix to add (cloudflare.com is Cloudflare's own property,
not a fronting target).

Ranges are the well-known published sets, embedded so detection works
offline (``--no-net`` over a captured catalog that already recorded IPs).

Sources (consulted at implementation time, not at runtime):
  - https://www.cloudflare.com/ips/  (IPv4 + IPv6)
  - https://api.fastly.com/public-ip-list
  - https://docs.aws.amazon.com/CloudFront/latest/DeveloperGuide/LocationsOfEdgeServers.html
  - Akamai edges are detected by hostname suffix (.akamai.net / .akamaiedge.net)
    in addition to the published ranges, since their range list rotates.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable, Optional

# --- Cloudflare (AS13335) — the headline fronting CDN. -------------------
CLOUDFLARE_V4 = [
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
]
CLOUDFLARE_V6 = [
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
    "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
]

# --- Fastly. --------------------------------------------------------------
FASTLY_V4 = [
    "23.235.32.0/20", "43.249.72.0/22", "103.244.50.0/24", "103.245.222.0/23",
    "103.245.224.0/24", "104.156.80.0/20", "151.101.0.0/16", "157.52.64.0/18",
    "167.82.0.0/17", "167.82.128.0/20", "167.82.160.0/20", "167.82.224.0/20",
    "172.111.64.0/18", "185.31.16.0/22", "199.27.72.0/21", "199.232.0.0/16",
]
FASTLY_V6 = ["2001:978::/32", "2001:978:2::/48", "2001:67c:44::/48",
             "2a04:4e40::/32", "2a04:4e40:0::/36", "2a04:4e40:4000::/36"]

# --- AWS CloudFront (a sample of the global ranges; the full list rotates,
#     so this is a conservative detector, not an exhaustive map). ---------
CLOUDFRONT_V4 = [
    "13.32.0.0/15", "13.34.0.0/15", "13.224.0.0/14", "52.46.0.0/18",
    "52.84.0.0/15", "99.84.0.0/16", "205.251.192.0/19", "205.251.224.0/22",
]
CLOUDFRONT_V6 = ["2600:9000::/28", "2a02:26f0::/32"]

# Hostname-suffix detectors (used when no IP is known — e.g. offline over a
# captured hostname that wasn't resolved). Akamai in particular is best
# detected by suffix.
CDN_HOST_SUFFIXES = {
    "akamai.net": "Akamai",
    "akamaiedge.net": "Akamai",
    "akamaihd.net": "Akamai",
    "akamaized.net": "Akamai",
    "edgesuite.net": "Akamai",
    "edgekey.net": "Akamai",
    "cloudfront.net": "CloudFront",
    "fastly.net": "Fastly",
    "fastlylb.net": "Fastly",
}


@dataclass(frozen=True)
class CDN:
    name: str
    asn: str  # the CDN's primary ASN, for evidence


_CLOUDFLARE = CDN(name="Cloudflare", asn="AS13335")
_FASTLY = CDN(name="Fastly", asn="AS54113")
_AKAMAI = CDN(name="Akamai", asn="AS20940")
_CLOUDFRONT = CDN(name="CloudFront", asn="AS16509")

# Pre-built networks (module load) so per-IP detection is a fast containment
# check, not a parse on every call.
_NETS_V4 = (
    [(_CLOUDFLARE, ipaddress.ip_network(c, strict=False)) for c in CLOUDFLARE_V4]
    + [(_FASTLY, ipaddress.ip_network(c, strict=False)) for c in FASTLY_V4]
    + [(_CLOUDFRONT, ipaddress.ip_network(c, strict=False)) for c in CLOUDFRONT_V4]
)
_NETS_V6 = (
    [(_CLOUDFLARE, ipaddress.ip_network(c, strict=False)) for c in CLOUDFLARE_V6]
    + [(_FASTLY, ipaddress.ip_network(c, strict=False)) for c in FASTLY_V6]
    + [(_CLOUDFRONT, ipaddress.ip_network(c, strict=False)) for c in CLOUDFRONT_V6]
)


def _ip_in_nets(ip: str, nets: Iterable) -> Optional[CDN]:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    for cdn, net in nets:
        if addr in net:
            return cdn
    return None


def detect_by_ip(ip: str) -> Optional[CDN]:
    """Return the CDN that owns ``ip``, or ``None`` if not a known CDN edge."""
    if ":" in ip:
        return _ip_in_nets(ip, _NETS_V6)
    return _ip_in_nets(ip, _NETS_V4)


def detect_by_host(host: str) -> Optional[CDN]:
    """Suffix-based CDN detection when no IP is available (offline path)."""
    h = (host or "").lower()
    for suffix, name in CDN_HOST_SUFFIXES.items():
        if h == suffix or h.endswith("." + suffix):
            if name == "Cloudflare":
                return _CLOUDFLARE
            if name == "Fastly":
                return _FASTLY
            if name == "Akamai":
                return _AKAMAI
            if name == "CloudFront":
                return _CLOUDFRONT
    return None


def detect(host: str, ips: Iterable[str] = ()) -> Optional[CDN]:
    """Detect the CDN for ``host``: try each resolved IP first, then suffix."""
    for ip in ips:
        cdn = detect_by_ip(ip)
        if cdn:
            return cdn
    return detect_by_host(host)


def is_frontable(host: str, ips: Iterable[str] = ()) -> bool:
    """A host is frontable if it sits on a CDN edge (SNI can be set
    independently of the tunneled destination)."""
    return detect(host, ips) is not None
