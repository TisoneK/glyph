"""TUI data adapters — pure views over the catalog (`glyph.db`).

No Textual here: each function turns catalog rows into
``(headers, rows)`` the dashboard can drop into a table, plus a
``summary()`` of headline counts. Kept pure so it's unit-testable and so
the analysis engine stays a headless backend (the TUI only reads).
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from glyph.catalog import Catalog
from glyph.catalog.normalize import template_path

Rows = Tuple[List[str], List[List[str]]]  # (headers, rows)


def clip(text: Optional[str], limit: int = 64) -> str:
    """Ellipsize long cell values so one long host/URL can't balloon a
    table column into the neighbors (Session 27)."""
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def human_size(n: Optional[int]) -> str:
    if not n:
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n/1024:.0f} KB"
    if n < 1024 ** 3:
        return f"{n/1024**2:.1f} MB"
    return f"{n/1024**3:.1f} GB"


def flow_type(flow) -> str:
    """Short resource type: playwright's tag, else derived from mime."""
    src = flow.source or ""
    if ":" in src:
        return src.split(":")[-1]
    mime = (flow.resp_mime or "").lower()
    if "html" in mime:
        return "document"
    if "javascript" in mime or mime.endswith("/js"):
        return "script"
    if "json" in mime:
        return "xhr"
    if "css" in mime:
        return "stylesheet"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("font/") or "font" in mime:
        return "font"
    return mime.split("/")[-1] or (src or "flow")


def _flow_size(flow) -> int:
    headers = {k.lower(): v for k, v in (flow.resp_headers or {}).items()}
    cl = headers.get("content-length")
    if cl and str(cl).isdigit():
        return int(cl)
    return len((flow.resp_body or "").encode("utf-8", "ignore"))


def summary(cat: Catalog) -> Dict[str, Any]:
    flows = cat.all_flows()
    by_type = Counter(flow_type(f) for f in flows)
    fields = [f for ep in cat.endpoints() if ep.id is not None
              for f in cat.fields_for_endpoint(ep.id)]
    enums = sum(1 for f in fields if f.is_enum_candidate)
    findings = cat.findings()
    from glyph.sensitive.scan import is_noise
    actionable = [f for f in findings if not is_noise(f)]
    by_sev = Counter(f.severity for f in actionable)
    labels = [lab for p in cat.pages() for lab in p.labels]
    by_tag = Counter((lab.get("tag") or "?") for lab in labels)
    dic = cat.dictionary()
    sni = cat.findings(kind="sni_bug_host")
    sni_by_sev = Counter(f.severity for f in sni)
    vpns = cat.vpn_configs()
    vpn_ok = sum(1 for c in vpns if c["decryption_status"] in ("success", "partial"))
    return {
        "flows": len(flows),
        "by_type": dict(by_type),
        "fields": len(fields),
        "enums": enums,
        "findings": len(actionable),
        "by_severity": dict(by_sev),
        "tracking_noise": len(findings) - len(actionable),
        "dom_labels": len(labels),
        "dom_by_tag": dict(by_tag),
        "decoded": len(dic),
        "decoded_review": sum(1 for d in dic if d.needs_review),
        "sni_candidates": len(sni),
        "sni_by_severity": dict(sni_by_sev),
        "vpn_configs": len(vpns),
        "vpn_decoded": vpn_ok,
        "target": cat.target(),
    }


def flow_rows(cat: Catalog, text_filter: Optional[str] = None) -> Rows:
    headers = ["#", "METHOD", "TYPE", "CODE", "SIZE", "URL"]
    rows: List[List[str]] = []
    flows = cat.all_flows()
    for f in flows:
        url = f.path or f.url
        if f.query:
            url += "?" + "&".join(f"{k}={v}" for k, v in list(f.query.items())[:3])
        if text_filter and text_filter.lower() not in (f.url + " " + f.method).lower():
            continue
        rows.append([str(f.id or ""), f.method, flow_type(f),
                     str(f.status or "—"), human_size(_flow_size(f)),
                     clip(url, 72)])
    return headers, rows


def flow_detail(cat: Catalog, flow_id: int) -> Optional[dict]:
    for f in cat.all_flows():
        if f.id == flow_id:
            return {
                "method": f.method, "url": f.url, "status": f.status,
                "req_headers": f.req_headers or {}, "req_body": f.req_body,
                "resp_headers": f.resp_headers or {}, "resp_body": f.resp_body,
                "resp_mime": f.resp_mime,
            }
    return None


def dom_rows(cat: Catalog) -> Rows:
    headers = ["#", "ELEMENT", "TEXT", "ATTRIBUTES"]
    rows: List[List[str]] = []
    i = 0
    for page in cat.pages():
        for lab in page.labels:
            i += 1
            attrs = " ".join(f"{k}={v}" for k, v in (lab.get("attrs") or {}).items())
            rows.append([str(i), lab.get("tag") or "?",
                         (lab.get("text") or "")[:60], attrs[:60]])
    return headers, rows


def schema_rows(cat: Catalog) -> Rows:
    headers = ["FIELD", "TYPE", "ENUM", "SOURCE"]
    rows: List[List[str]] = []
    for ep in cat.endpoints():
        if ep.id is None:
            continue
        src = f"{ep.method} {ep.path_template}"
        for f in cat.fields_for_endpoint(ep.id):
            enum = f"{f.distinct_count} values" if f.is_enum_candidate else "—"
            rows.append([f.json_path, f.json_type, enum, src])
    return headers, rows


def sensitive_rows(cat: Catalog, include_noise: bool = False) -> Rows:
    from glyph.sensitive.scan import is_noise
    from glyph.cli._format import mask_value
    headers = ["#", "SEVERITY", "CATEGORY", "KIND", "HOST", "LOCATION", "VALUE"]
    kind_label = {"sensitive_data": "data", "sensitive_endpoint": "endpoint",
                  "risk": "risk"}
    rows: List[List[str]] = []
    i = 0
    for f in cat.findings():
        if not include_noise and is_noise(f):
            continue
        i += 1
        loc = "" if f.location == "endpoint" else f.location
        rows.append([str(i), f.severity.upper(), f.category,
                     kind_label.get(f.kind, f.kind), clip(f.host, 36),
                     loc, mask_value(f.value_sample)])
    return headers, rows


def rosetta_rows(cat: Catalog) -> Rows:
    headers = ["PATH", "CODE", "MEANING", "CONF", "STRATEGY", "STATUS"]
    rows: List[List[str]] = []
    for d in cat.dictionary():
        rows.append([clip(d.json_path, 48), repr(d.code), str(d.meaning),
                     f"{d.confidence:.2f}", d.strategy,
                     "REVIEW" if d.needs_review else "ok"])
    return headers, rows


_SNI_CAT_LABEL = {
    "sni_zero_rated": "zero-rated",
    "sni_frontable_cdn": "cdn-front",
    "sni_shared_cert": "shared-cert",
    "sni_candidate": "candidate",
}


def snihunt_rows(cat: Catalog) -> Rows:
    """SNI bug-host candidates ranked by score (ADR-10). Compact columns —
    HOST / STATUS / IP / CDN / TYPE / SIGNALS — not the old wall-of-prose
    evidence. STATUS is the HTTP code from the probe (— when not probed)."""
    from glyph.snihunt import parse_evidence
    headers = ["SEV", "SCR", "SNI HOST", "STATUS", "IP", "CDN", "TYPE", "SIGNALS"]
    rows: List[List[str]] = []
    findings = cat.findings(kind="sni_bug_host")
    findings = sorted(findings, key=lambda f: -(f.score or 0))
    for f in findings:
        ev = parse_evidence(f.evidence or "")
        ip = ev.get("ip", "") or "—"
        cdn = ev.get("cdn", "") or "—"
        status = ev.get("http_status")
        status_str = str(status) if status is not None else "—"
        sigs = []
        if ev.get("captured"): sigs.append(f"cap×{ev['captured']}")
        if ev.get("zero_rating"): sigs.append("zero:" + ",".join(ev["zero_rating"][:2]))
        if ev.get("wildcard"): sigs.append("wildcard")
        if ev.get("shared_cert"): sigs.append(f"shared:{ev['shared_cert']}")
        if ev.get("reverse_siblings"): sigs.append(f"rip+{ev['reverse_siblings']}")
        if ev.get("reverse_sourced"): sigs.append("rip-sourced")
        if ev.get("probe_ok"): sigs.append("cert✓")
        rows.append([f.severity.upper(), str(f.score or 0), clip(f.host, 44),
                     status_str, ip, cdn,
                     _SNI_CAT_LABEL.get(f.category, f.category),
                     " ".join(sigs) or "—"])
    return headers, rows


def vpndec_rows(cat: Catalog) -> Rows:
    """Decoded VPN configs (ADR-11). One row per decoded file."""
    headers = ["STATUS", "FORMAT", "HOST", "PORT", "PROTO", "SNI", "FILE"]
    rows: List[List[str]] = []
    for cfg in cat.vpn_configs():
        mark = {"success": "✓", "partial": "◐", "not_encrypted": "○",
                "failed": "✗", "no_decryptor": "—"}.get(
            cfg["decryption_status"], "?")
        rows.append([
            f"{mark} {cfg['decryption_status']}",
            cfg["format"],
            clip(cfg["host"] or "—", 36),
            str(cfg["port"] or "—"),
            cfg["protocol"] or "—",
            clip(cfg["sni"] or "—", 30),
            clip(cfg["filename"], 32),
        ])
    return headers, rows
