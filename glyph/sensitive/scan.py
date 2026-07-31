"""Scan orchestrator — run all three flag stages over a catalog.

Walks captured queries, headers, and bodies for sensitive data; classifies
sensitive endpoints; derives passive risk indicators. Writes everything to
the catalog's findings table (idempotent: a re-scan clears first). Values
are recorded intact — flag and locate, never redact at rest.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

from glyph.catalog import FINDING_SENSITIVE_DATA, Catalog, Finding, severity_rank
from glyph.sensitive import endpoints as endpoints_mod
from glyph.sensitive import party as party_mod
from glyph.sensitive import risk as risk_mod
from glyph.sensitive.detectors import _SECRET_NAME, scan_value

_AUTH_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key",
                 "x-auth-token", "x-access-token", "proxy-authorization"}


def _walk_scalars(value: Any, path: str) -> Iterable[Tuple[str, str, Any]]:
    """Yield ``(json_path, leaf_name, scalar_value)`` for a parsed doc."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk_scalars(v, f"{path}.{k}")
    elif isinstance(value, list):
        for item in value:
            yield from _walk_scalars(item, f"{path}[]")
    else:
        leaf = path.rstrip("[]").split(".")[-1]
        yield path, leaf, value


def _parse_json(body: str, mime: str) -> Any:
    if not body:
        return None
    looks_json = (mime or "").endswith("json") or body.lstrip()[:1] in "{["
    if not looks_json:
        return None
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return None


def scan_data(catalog: Catalog, target: Optional[str] = None) -> List[Finding]:
    """Detect sensitive data across queries, headers, and bodies."""
    out: List[Finding] = []

    def add(category: str, sev: str, location: str, ep_id, value: str,
            where: str, host: str):
        out.append(Finding(
            kind=FINDING_SENSITIVE_DATA, category=category, severity=sev,
            location=location, endpoint_id=ep_id,
            evidence=f"{category} in {where}", value_sample=str(value)[:512],
            party=party_mod.classify(host, target), host=host,
        ))

    for ep in catalog.endpoints():
        for flow in catalog.flows_for_endpoint(ep.id):
            # Query parameters.
            for k, v in (flow.query or {}).items():
                for cat, sev, val in scan_value(k, v):
                    add(cat, sev, f"query:{k}", ep.id, val,
                        f"query '{k}' of {ep.key}", ep.host)
            # Auth-ish headers only (avoid noise on benign headers).
            for hdrs in (flow.req_headers, flow.resp_headers):
                for hk, hv in (hdrs or {}).items():
                    if hk.lower() in _AUTH_HEADERS or _SECRET_NAME.search(hk):
                        for cat, sev, val in scan_value(hk, hv):
                            add(cat, sev, f"header:{hk.lower()}", ep.id, val,
                                f"header '{hk}' of {ep.key}", ep.host)
            # Bodies: JSON walked field-by-field; other text scanned raw.
            for body, mime in ((flow.req_body, "application/json"),
                               (flow.resp_body, flow.resp_mime)):
                doc = _parse_json(body or "", mime or "")
                if doc is not None:
                    for jpath, leaf, val in _walk_scalars(doc, "$"):
                        for cat, sev, mval in scan_value(leaf, val):
                            add(cat, sev, jpath, ep.id, mval,
                                f"{jpath} of {ep.key}", ep.host)
                elif body and (mime or "").startswith("text"):
                    for cat, sev, mval in scan_value("", body):
                        add(cat, sev, f"body:{flow.path}", ep.id, mval,
                            f"response body of {ep.key}", ep.host)
    return out


def run_scan(catalog: Catalog) -> Dict[str, Any]:
    """Run every flag stage and persist findings. Returns a summary."""
    catalog.clear_findings()
    target = catalog.target()
    data = scan_data(catalog, target)
    for f in data:
        catalog.add_finding(f)
    for f in endpoints_mod.classify(catalog, target):
        catalog.add_finding(f)
    for f in risk_mod.assess(catalog, data, target):
        catalog.add_finding(f)
    return summarize(catalog)


def is_noise(finding) -> bool:
    """A finding is 'noise' only when it's hygiene chatter on a known
    tracking/ad vendor — NOT merely because its host is third-party.
    Anything carrying real data/behavior is never noise."""
    if finding.kind == FINDING_SENSITIVE_DATA:
        return False
    if finding.category in ("unauthenticated_sensitive_data",
                            "sensitive_data_in_url", "verbose_error"):
        return False
    return party_mod.is_tracking_vendor(finding.host)


def summarize(catalog: Catalog) -> Dict[str, Any]:
    findings = catalog.findings()
    by_kind: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    by_party: Dict[str, int] = {}
    actionable_by_severity: Dict[str, int] = {}
    noise = 0
    for f in findings:
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        by_party[f.party or "unknown"] = by_party.get(f.party or "unknown", 0) + 1
        if is_noise(f):
            noise += 1
        else:
            actionable_by_severity[f.severity] = \
                actionable_by_severity.get(f.severity, 0) + 1

    def sevmap(src: Dict[str, int]) -> Dict[str, int]:
        return {s: src[s] for s in ("critical", "high", "medium", "low")
                if src.get(s)}

    return {
        "total": len(findings),
        "target": catalog.target(),
        "by_kind": by_kind,
        "by_severity": sevmap(by_severity),
        "by_party": by_party,
        # Actionable = everything except tracking/ad hygiene noise.
        "actionable_total": len(findings) - noise,
        "actionable_by_severity": sevmap(actionable_by_severity),
        "tracking_noise": noise,
    }
