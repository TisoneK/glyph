"""Playwright driver — drive a URL and capture API + DOM (optional backend).

Requires the ``live`` extra (``pip install glyph-re[live]`` plus
``playwright install chromium``). Imports cleanly without Playwright; the
dependency is checked only when :func:`capture_url` is called.
"""
from __future__ import annotations

from typing import List, Optional

from glyph.catalog import Catalog, Flow, PageObservation
from glyph.capture.snapshot import harvest_labels, plain_text


def capture_url(catalog: Catalog, url: str,
                wait_selector: Optional[str] = None,
                timeout_ms: int = 15000) -> None:
    """Load ``url`` headless, recording XHR/fetch flows and the rendered DOM.

    Raises :class:`RuntimeError` with install guidance if Playwright is
    missing, so the base package never hard-depends on it.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised only with extra
        raise RuntimeError(
            "Playwright is not installed. Install the live extra:\n"
            "  pip install 'glyph-re[live]' && playwright install chromium"
        ) from exc

    captured: List[Flow] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        def on_response(response) -> None:
            req = response.request
            if req.resource_type not in ("xhr", "fetch", "document"):
                return
            try:
                body = response.text()
            except Exception:
                body = None
            captured.append(Flow(
                method=req.method, url=response.url, host="", path="",
                req_headers=dict(req.headers), status=response.status,
                resp_headers=dict(response.headers), resp_body=body,
                resp_mime=(response.headers.get("content-type") or "")
                .split(";")[0] or None,
                source="playwright",
            ))

        page.on("response", on_response)
        page.goto(url, timeout=timeout_ms, wait_until="networkidle")
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=timeout_ms)
        html = page.content()
        browser.close()

    for flow in captured:
        catalog.add_flow(flow)
    labels = harvest_labels(html)
    catalog.add_page(PageObservation(
        url=url, html=html, text=plain_text(html), labels=labels,
    ))
