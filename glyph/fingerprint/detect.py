"""Backend fingerprinting — identify a host's stack from response signals.

Domain-neutral header/cookie heuristics: Server, X-Powered-By, generator
headers, and session-cookie names each betray a framework family. Runs
over whatever flows the catalog already holds — no extra requests.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List

from glyph.catalog import Catalog

# Session-cookie name -> framework.
_COOKIE_FAMILY = {
    "phpsessid": "PHP",
    "laravel_session": "Laravel (PHP)",
    "ci_session": "CodeIgniter (PHP)",
    "jsessionid": "Java (Servlet)",
    "connect.sid": "Express (Node.js)",
    "csrftoken": "Django (Python)",
    "sessionid": "Django (Python)",
    "_rails_session": "Rails (Ruby)",
    "asp.net_sessionid": "ASP.NET",
    ".aspxauth": "ASP.NET",
}
_POWERED = {
    "php": "PHP",
    "express": "Express (Node.js)",
    "asp.net": "ASP.NET",
    "next.js": "Next.js",
    "servlet": "Java (Servlet)",
}


def _cookie_names(set_cookie: str) -> List[str]:
    names = []
    for part in re.split(r",(?=[^ ;]+=)", set_cookie or ""):
        m = re.match(r"\s*([^=;]+)=", part)
        if m:
            names.append(m.group(1).strip().lower())
    return names


def fingerprint(catalog: Catalog) -> Dict[str, Dict[str, Any]]:
    """Return ``{host: {server, powered_by, frameworks, evidence}}``."""
    by_host: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"server": None, "powered_by": None,
                 "frameworks": set(), "evidence": []})
    for flow in catalog.all_flows():
        host = flow.host
        rec = by_host[host]
        headers = {k.lower(): v for k, v in (flow.resp_headers or {}).items()}

        if not rec["server"] and headers.get("server"):
            rec["server"] = headers["server"]
            rec["evidence"].append(f"Server: {headers['server']}")
        powered = headers.get("x-powered-by")
        if powered and not rec["powered_by"]:
            rec["powered_by"] = powered
            rec["evidence"].append(f"X-Powered-By: {powered}")
            for needle, fam in _POWERED.items():
                if needle in powered.lower():
                    rec["frameworks"].add(fam)
        if headers.get("x-aspnet-version"):
            rec["frameworks"].add("ASP.NET")
        if headers.get("x-generator"):
            rec["evidence"].append(f"X-Generator: {headers['x-generator']}")

        for name in _cookie_names(headers.get("set-cookie", "")):
            if name in _COOKIE_FAMILY:
                rec["frameworks"].add(_COOKIE_FAMILY[name])
                rec["evidence"].append(f"cookie {name} -> {_COOKIE_FAMILY[name]}")

    # Freeze sets to sorted lists and de-dup evidence.
    out: Dict[str, Dict[str, Any]] = {}
    for host, rec in by_host.items():
        out[host] = {
            "server": rec["server"],
            "powered_by": rec["powered_by"],
            "frameworks": sorted(rec["frameworks"]),
            "evidence": list(dict.fromkeys(rec["evidence"])),
        }
    return out
