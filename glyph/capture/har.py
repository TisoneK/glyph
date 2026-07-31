"""HAR ingestion — the dependency-free, universal capture path.

Every browser's devtools, mitmproxy (``--set hardump``), Charles, Fiddler
and Proxyman can export a HAR. Glyph consumes that directly, so the base
tool needs no proxy or browser to start cataloguing a target.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from glyph.capture.snapshot import harvest_labels
from glyph.catalog import Catalog, Flow, PageObservation


def _headers_to_dict(headers: Optional[List[Dict[str, Any]]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for h in headers or []:
        name = h.get("name")
        if name and not name.startswith(":"):  # skip HTTP/2 pseudo-headers
            out[name] = h.get("value", "")
    return out


def flow_from_entry(entry: Dict[str, Any]) -> Optional[Flow]:
    """Convert one HAR entry to a :class:`Flow` (``None`` if malformed)."""
    req = entry.get("request") or {}
    resp = entry.get("response") or {}
    url = req.get("url")
    method = req.get("method")
    if not url or not method:
        return None
    content = resp.get("content") or {}
    post = req.get("postData") or {}
    return Flow(
        method=method,
        url=url,
        host="",  # derived by the catalog from the URL
        path="",
        req_headers=_headers_to_dict(req.get("headers")),
        req_body=post.get("text"),
        status=resp.get("status"),
        resp_headers=_headers_to_dict(resp.get("headers")),
        resp_body=content.get("text"),
        resp_mime=(content.get("mimeType") or "").split(";")[0] or None,
        started_at=entry.get("startedDateTime"),
        source="har",
    )


def ingest_har(catalog: Catalog, har_path: str,
               harvest_html: bool = True, *,
               clear: bool = False) -> Dict[str, int]:
    """Load a HAR file into the catalog.

    Returns counts of ``{"flows", "pages"}`` added. When ``harvest_html``
    is set, ``text/html`` responses also become
    :class:`PageObservation`\\ s whose labels feed Rosetta's UI side.

    Multi-target (ADR-12): infers the target host (first HTML document's
    host, else the most-seen host), activates it via :meth:`set_target`
    (only if no target is already active — ``run har`` pre-activates), and
    — when ``clear=True`` — wipes that target's old rows first so a re-run
    is idempotent without touching other targets. ``capture har`` leaves
    ``clear=False`` (the default) so repeated ingestions accumulate.
    """
    with open(har_path, "r", encoding="utf-8") as fh:
        har = json.load(fh)
    entries = (har.get("log") or {}).get("entries") or []
    from urllib.parse import urlparse
    from collections import Counter

    # Pass 1: parse entries + infer the target host. We do NOT write yet —
    # clear (if requested) must happen between target activation and the
    # first add_flow, otherwise we'd delete the rows we just wrote.
    parsed: List[Dict[str, Any]] = []
    hosts: Counter = Counter()
    first_doc_host = None
    for entry in entries:
        flow = flow_from_entry(entry)
        if flow is None:
            continue
        host = urlparse(flow.url).hostname
        if host:
            hosts[host] += 1
            if first_doc_host is None and flow.resp_mime == "text/html":
                first_doc_host = host
        rec: Dict[str, Any] = {"flow": flow}
        if harvest_html and flow.resp_mime == "text/html" and flow.resp_body:
            labels = harvest_labels(flow.resp_body)
            if labels:
                rec["page"] = PageObservation(
                    url=flow.url, html=None, text=None,
                    labels=labels, observed_at=flow.started_at,
                )
        parsed.append(rec)

    # Activate + (optionally) clear the target before writing.
    if catalog.target_id() is None:
        target = first_doc_host or (hosts.most_common(1)[0][0] if hosts else None)
        if target:
            catalog.set_target(target)
    if clear and catalog.target_id() is not None:
        catalog.clear_target()

    # Pass 2: write.
    flows = 0
    pages = 0
    for rec in parsed:
        catalog.add_flow(rec["flow"])
        flows += 1
        if "page" in rec:
            catalog.add_page(rec["page"])
            pages += 1
    return {"flows": flows, "pages": pages}
