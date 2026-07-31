"""Passive risk indicators — flagged from captured traffic, never exploited.

These are *observations that warrant a look*, not confirmed vulnerabilities
and never active probes: secrets/PII carried in URLs, sensitive data on
unauthenticated endpoints, wildcard CORS, missing security headers, verbose
errors, and guessable object ids (IDOR candidates). For authorized,
defensive assessment.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from glyph.catalog import (
    FINDING_RISK,
    SEV_CRITICAL,
    SEV_HIGH,
    SEV_LOW,
    SEV_MEDIUM,
    Catalog,
    Finding,
)
from glyph.sensitive import party as party_mod

_STACK_TRACE = re.compile(
    r"(Traceback \(most recent call last\)|"
    r"\bat [\w.$]+\([\w.]+:\d+\)|"          # Java/Kotlin stack frames
    r"\bat [\w.]+\.<\w+>|"
    r"System\.\w+Exception|"                 # .NET
    r"\bORA-\d{5}|SQLSTATE\[|"               # Oracle / SQL
    r"Warning: \w+\(\) |Fatal error: |"      # PHP
    r"org\.springframework\.|"               # Spring
    r"\.py\", line \d+, in )")
_SEC_HEADERS = {
    "strict-transport-security": ("hsts", SEV_MEDIUM),
    "content-security-policy": ("csp", SEV_LOW),
    "x-content-type-options": ("x_content_type_options", SEV_LOW),
    "x-frame-options": ("x_frame_options", SEV_LOW),
}
_INT = re.compile(r"^\d{1,7}$")


def assess(catalog: Catalog, data_findings: List[Finding],
           target: Optional[str] = None) -> List[Finding]:
    """Return risk findings, cross-referencing the data findings."""
    out: List[Finding] = []
    out += _sensitive_in_url(data_findings)
    out += _unauthenticated_sensitive_data(catalog, data_findings, target)
    out += _cors_and_headers(catalog, target)
    out += _verbose_errors(catalog, target)
    out += _guessable_ids(catalog, target)
    return out


def _sensitive_in_url(data_findings: List[Finding]) -> List[Finding]:
    out = []
    for f in data_findings:
        if f.location.startswith("query:"):
            out.append(Finding(
                kind=FINDING_RISK, category="sensitive_data_in_url",
                severity=SEV_HIGH, location=f.location,
                endpoint_id=f.endpoint_id,
                evidence=f"{f.category} carried in a URL query parameter "
                         f"({f.location}) — leaks via logs, history, Referer",
                value_sample=f.value_sample,
                party=f.party,  # inherit the data finding's party
            ))
    return out


def _unauthenticated_sensitive_data(catalog: Catalog,
                                    data_findings: List[Finding],
                                    target: Optional[str] = None) -> List[Finding]:
    from glyph.auth import analyze
    auth = analyze(catalog)
    endpoints = {e.id: e for e in catalog.endpoints()}
    # endpoints whose *response body* carries sensitive data
    body_sensitive: Dict[int, List[Finding]] = {}
    for f in data_findings:
        if f.endpoint_id is not None and f.location.startswith("$"):
            body_sensitive.setdefault(f.endpoint_id, []).append(f)

    out = []
    for ep_id, findings in body_sensitive.items():
        ep = endpoints.get(ep_id)
        if ep is None:
            continue
        schemes = auth.get(ep.key, {}).get("schemes", [])
        if schemes and schemes != ["none observed"]:
            continue  # endpoint is authenticated
        cats = sorted({f.category for f in findings})
        critical = any(f.severity == SEV_CRITICAL
                       or f.category in ("credit_card", "password",
                                         "private_key", "secret_token")
                       for f in findings)
        out.append(Finding(
            kind=FINDING_RISK, category="unauthenticated_sensitive_data",
            severity=SEV_CRITICAL if critical else SEV_HIGH,
            location="endpoint", endpoint_id=ep_id,
            evidence=f"{ep.key} returns sensitive data ({', '.join(cats)}) "
                     f"with no authentication observed",
            party=party_mod.classify(ep.host, target),
        ))
    return out


def _cors_and_headers(catalog: Catalog,
                      target: Optional[str] = None) -> List[Finding]:
    out: List[Finding] = []
    seen_html_hosts: set = set()
    header_seen: Dict[str, set] = {}
    cors_flagged: set = set()

    for flow in catalog.all_flows():
        headers = {k.lower(): v for k, v in (flow.resp_headers or {}).items()}
        # Wildcard CORS (worse with credentials).
        aco = headers.get("access-control-allow-origin")
        if aco == "*" and flow.host not in cors_flagged:
            cors_flagged.add(flow.host)
            creds = headers.get("access-control-allow-credentials", "").lower() == "true"
            out.append(Finding(
                kind=FINDING_RISK, category="wildcard_cors",
                severity=SEV_CRITICAL if creds else SEV_MEDIUM,
                location="header:access-control-allow-origin",
                evidence=f"{flow.host} returns Access-Control-Allow-Origin: *"
                         + (" WITH credentials" if creds else ""),
                party=party_mod.classify(flow.host, target),
            ))
        # Track security-header presence on HTML documents per host.
        if (flow.resp_mime or "") == "text/html":
            seen_html_hosts.add(flow.host)
            present = header_seen.setdefault(flow.host, set())
            for h in _SEC_HEADERS:
                if h in headers:
                    present.add(h)

    for host in sorted(seen_html_hosts):
        present = header_seen.get(host, set())
        for header, (slug, sev) in _SEC_HEADERS.items():
            if header not in present:
                out.append(Finding(
                    kind=FINDING_RISK, category="missing_security_header",
                    severity=sev, location=f"header:{header}",
                    evidence=f"{host} HTML responses never set {header}",
                    party=party_mod.classify(host, target),
                ))
    return out


def _verbose_errors(catalog: Catalog,
                    target: Optional[str] = None) -> List[Finding]:
    out = []
    flagged: set = set()
    for flow in catalog.all_flows():
        body = flow.resp_body or ""
        if not body:
            continue
        key = (flow.host, flow.path)
        if key in flagged:
            continue
        if _STACK_TRACE.search(body[:20000]):
            flagged.add(key)
            snippet = _STACK_TRACE.search(body[:20000]).group(0)
            out.append(Finding(
                kind=FINDING_RISK, category="verbose_error",
                severity=SEV_MEDIUM, location=f"response:{flow.path}",
                evidence=f"{flow.host}{flow.path} response leaks a stack "
                         f"trace / server error detail",
                value_sample=snippet,
            ))
    return out


def _guessable_ids(catalog: Catalog,
                   target: Optional[str] = None) -> List[Finding]:
    out = []
    for ep in catalog.endpoints():
        if "{id}" not in (ep.path_template or ""):
            continue
        ids = set()
        for flow in catalog.flows_for_endpoint(ep.id):
            for seg in (flow.path or "").split("/"):
                if _INT.match(seg) and int(seg) < 1_000_000:
                    ids.add(int(seg))
        if len(ids) >= 2:
            out.append(Finding(
                kind=FINDING_RISK, category="guessable_object_id",
                severity=SEV_MEDIUM, location="endpoint", endpoint_id=ep.id,
                evidence=f"{ep.key} uses small sequential-looking numeric ids "
                         f"(e.g. {sorted(ids)[:5]}) — IDOR/BOLA candidate; "
                         f"verify object-level authorization",
                party=party_mod.classify(ep.host, target),
            ))
    return out
