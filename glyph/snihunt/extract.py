"""Extract the observed SNI/host surface from a captured catalog.

Pure: no network. Walks every captured flow and collects the distinct
hostnames a browser actually sent an SNI for, plus any resolved IPs the
capture happened to record (in request headers like ``X-Resolved-IP`` /
``Cf-Connecting-Ip``, or in a ``host`` that is itself an IP literal).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from glyph.catalog import Catalog
from glyph.catalog.normalize import registrable_domain

# Request headers that sometimes carry the resolved upstream IP, which lets
# CDN detection run on a capture that didn't itself resolve the host.
_IP_HEADERS = ("cf-connecting-ip", "x-forwarded-for", "x-resolved-ip",
               "x-real-ip", "x-originating-ip")


def _maybe_ip(value: str) -> Optional[str]:
    """Return ``value`` if it parses as an IP literal, else ``None``."""
    import ipaddress
    v = (value or "").split(",")[0].strip()
    if not v:
        return None
    try:
        ipaddress.ip_address(v)
        return v
    except ValueError:
        return None


@dataclass
class HostInfo:
    """One observed hostname + what we know about it from the capture."""

    host: str
    registrable: str
    flow_ids: List[int] = field(default_factory=list)
    captured_ips: Set[str] = field(default_factory=set)
    # methods seen on this host (a hint: GET-only asset hosts vs API hosts)
    methods: Set[str] = field(default_factory=set)

    @property
    def observed_in_capture(self) -> bool:
        return bool(self.flow_ids)


def extract_hosts(cat: Catalog) -> List[HostInfo]:
    """Walk every flow and return the distinct observed hostnames.

    The browser's SNI for a flow IS ``flow.host`` (Playwright/the HAR records
    the URL's authority). We also scan request headers for any resolved IP
    the surface happened to expose, so CDN detection can run offline.
    """
    by_host: Dict[str, HostInfo] = {}
    for flow in cat.all_flows():
        host = (flow.host or "").split(":")[0].strip(".").lower()
        if not host:
            continue
        info = by_host.get(host)
        if info is None:
            info = HostInfo(host=host, registrable=registrable_domain(host))
            by_host[host] = info
        if flow.id is not None:
            info.flow_ids.append(flow.id)
        if flow.method:
            info.methods.add(flow.method.upper())
        # Hunt for any IP literal the capture exposed for this host.
        for hk, hv in (flow.req_headers or {}).items():
            if hk.lower() in _IP_HEADERS:
                ip = _maybe_ip(hv)
                if ip:
                    info.captured_ips.add(ip)
        # A host that IS an IP literal (rare but possible) records itself.
        ip = _maybe_ip(host)
        if ip:
            info.captured_ips.add(ip)
    # Stable order: most-observed first, then alphabetical.
    return sorted(by_host.values(),
                  key=lambda h: (-len(h.flow_ids), h.host))
