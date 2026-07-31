"""Playwright driver — drive a URL and capture API + DOM (optional backend).

Requires the ``live`` extra (``pip install glyph-re[live]`` plus
``playwright install chromium``). Imports cleanly without Playwright; the
dependency is checked only when :func:`capture_url` is called.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlparse, unquote

from glyph.catalog import Catalog, Flow, PageObservation
from glyph.capture.snapshot import harvest_labels, plain_text


def _parse_proxy(proxy: str) -> dict:
    """Parse a proxy URL into Playwright's ``{server, username, password}`` form.

    Accepts ``http://user:pass@host:port``, ``http://host:port``,
    ``socks5://host:port``, etc. Per ADR-3, Glyph stays neutral about *which*
    proxy/relay is used — the caller supplies whatever upstream they have
    (a residential proxy, a bore.pub tunnel, a commercial SOCKS5, an upstream
    mitmproxy), and the driver just routes through it.
    """
    p = urlparse(proxy)
    if not p.scheme or not p.hostname:
        raise ValueError(
            f"proxy must be a full URL like 'http://host:port' or "
            f"'http://user:pass@host:port' — got {proxy!r}")
    server = f"{p.scheme}://{p.hostname}"
    if p.port:
        server += f":{p.port}"
    out = {"server": server}
    if p.username:
        out["username"] = unquote(p.username)
    if p.password:
        out["password"] = unquote(p.password)
    return out


def _explore_round(page, timeout_ms: int) -> None:
    """One target-agnostic interaction round: scroll + click generic elements.

    Designed to surface lazy-loaded endpoints (live-odds feeds, expand-on-
    click markets, infinite scroll) without any target-specific selectors.
    Every step is best-effort — a failure (element not clickable, scroll
    blocked) is swallowed so the round continues.
    """
    import secrets as _secrets
    try:
        # Scroll down in steps to trigger infinite-scroll / lazy loaders.
        for _ in range(3):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(800)
        # Scroll back up (some SPAs load above-the-fold lazily on re-entry).
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)
        # Click a few generic clickable elements. We pick from elements that
        # look interactive (cursor:pointer, role=link/button, or tag a/button)
        # choosing pseudo-randomly so repeated runs explore different paths.
        candidates = page.query_selector_all(
            "a, button, [role='button'], [role='link'], "
            "[onclick], [class*='item'], [class*='row'], [class*='event'], "
            "[class*='league'], [class*='market']")
        # Filter to visible, then pick a few at random.
        visible = []
        for el in candidates[:200]:  # cap to keep it fast
            try:
                if el.is_visible():
                    visible.append(el)
            except Exception:
                pass
        if visible:
            # Pick up to 3 distinct elements pseudo-randomly.
            picked = set()
            for _ in range(min(3, len(visible))):
                idx = _secrets.randbelow(len(visible))
                if idx in picked:
                    continue
                picked.add(idx)
                try:
                    visible[idx].click(timeout=min(timeout_ms, 5000))
                    page.wait_for_timeout(1500)
                except Exception:
                    pass  # not clickable / covered / opens new tab — skip
    except Exception:
        pass  # exploration is best-effort; never fail the capture


def capture_url(catalog: Catalog, url: str,
                wait_selector: Optional[str] = None,
                timeout_ms: int = 15000,
                proxy: Optional[str] = None,
                settle_ms: int = 3000,
                explore: int = 0) -> dict:
    """Load ``url`` headless, recording XHR/fetch flows and the rendered DOM.

    Raises :class:`RuntimeError` with install guidance if Playwright is
    missing, so the base package never hard-depends on it.

    ``proxy`` (optional) routes the headless browser through an upstream
    proxy — useful for geo-blocked targets (the host's native egress can't
    reach them) or for routing through a residential IP. Accepts the full
    ``http://user:pass@host:port`` form. Per ADR-3, Glyph records the
    resulting reachability as a neutral catalog attribute; it does not
    own or name the proxy/relay tool itself.

    ``wait_selector`` (optional) waits for a CSS selector that marks
    "content settled" — essential for SPAs whose real data loads via
    late XHR/fetch after the initial HTML. Without it, capture races the
    app's bootstrap and records only the shell.

    ``settle_ms`` (default 3s) is a final quiet delay after the wait
    condition, so late-fired XHR responses land in the catalog. SPAs
    often issue follow-up calls (websocket frames, polling, lazy-loaded
    markets) that arrive after the first render.

    ``explore`` (default 0) is the number of target-agnostic interaction
    rounds to run after the initial load settles. Each round: scroll the
    page in steps, click a few generic clickable elements (links, buttons,
    list rows with cursor:pointer), and wait briefly for the resulting
    XHR/fetch to fire. This surfaces lazy-loaded endpoints (live-odds
    feeds, expand-on-click markets, infinite-scroll content) that a pure
    load capture misses. The interaction is deliberately generic — no
    target-specific selectors — so it works on any SPA. Set higher (3-5)
    for content-rich dashboards.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised only with extra
        raise RuntimeError(
            "Playwright is not installed. Install the live extra:\n"
            "  pip install 'glyph-re[live]' && playwright install chromium"
        ) from exc

    captured: List[Flow] = []
    launch_kwargs = {"headless": True}
    if proxy:
        launch_kwargs["proxy"] = _parse_proxy(proxy)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_kwargs)
        page = browser.new_page()

        def on_response(response) -> None:
            # Capture EVERYTHING that moves — do not pre-filter by resource
            # type. Sites hide API calls behind non-xhr/fetch types (a
            # `script`-typed endpoint that returns JSON, a `other`-typed
            # beacon, a websocket upgrade). The capture layer's job is to
            # record; the catalog/analysis stages decide what's interesting.
            # The resource type is preserved in `source` as
            # "playwright:<resource_type>" so downstream stages can filter
            # without losing the data.
            req = response.request
            rtype = req.resource_type or "unknown"
            try:
                body = response.text()
            except Exception:
                # Binary / non-text bodies (images, fonts, wasm) — record
                # metadata only, not the body. Still an API candidate if
                # the mime is json-ish.
                body = None
            captured.append(Flow(
                method=req.method, url=response.url, host="", path="",
                req_headers=dict(req.headers), status=response.status,
                resp_headers=dict(response.headers), resp_body=body,
                resp_mime=(response.headers.get("content-type") or "")
                .split(";")[0] or None,
                source=f"playwright:{rtype}",
            ))

        page.on("response", on_response)

        # WebSockets: record each frame as a flow so streaming/real-time
        # API surfaces (live odds, score updates, push channels) are
        # captured, not just the upgrade handshake. The frame's payload
        # goes in resp_body; the URL is the WS endpoint.
        def on_websocket(ws) -> None:
            ws_url = getattr(ws, "url", "")
            def on_frame_sent(payload, *a, **kw):
                captured.append(Flow(
                    method="WS_SEND", url=ws_url, host="", path="",
                    query="", req_headers={}, req_body=payload if isinstance(payload, str) else None,
                    status=0, resp_headers={}, resp_body=None,
                    resp_mime="websocket", source="playwright:websocket",
                ))
            def on_frame_received(payload, *a, **kw):
                captured.append(Flow(
                    method="WS_RECV", url=ws_url, host="", path="",
                    query="", req_headers={}, req_body=None,
                    status=0, resp_headers={}, resp_body=payload if isinstance(payload, str) else None,
                    resp_mime="websocket", source="playwright:websocket",
                ))
            try:
                ws.on("framesent", on_frame_sent)
                ws.on("framereceived", on_frame_received)
            except Exception:
                pass  # older Playwright APIs differ; best-effort
        try:
            page.on("websocket", on_websocket)
        except Exception:
            pass  # websocket event not available in this Playwright version

        # 'networkidle' never fires for SPAs with long-lived connections
        # (websockets, long-polling) or behind slow proxy tunnels. Use
        # 'domcontentloaded' as the early milestone, then wait for a
        # caller-supplied selector that marks "content settled." The whole
        # navigation+interaction block is best-effort: a failure (dead
        # proxy, block page, timeout) must not throw away whatever was
        # already captured — we record the error and still persist flows.
        nav_error: Optional[str] = None
        html = ""
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception:
                    pass  # selector may never appear (block page, slow render)
            else:
                try:
                    page.wait_for_load_state("load", timeout=timeout_ms)
                except Exception:
                    pass
            # Settle: let late-fired XHR responses land in the catalog.
            if settle_ms > 0:
                page.wait_for_timeout(settle_ms)
            # Explore: target-agnostic interaction to surface lazy-loaded
            # endpoints (live feeds, expand-on-click, infinite scroll).
            for _ in range(max(0, explore)):
                _explore_round(page, timeout_ms)
        except Exception as exc:
            nav_error = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        try:
            html = page.content()
        except Exception:
            pass  # page may be unusable after a nav failure
        browser.close()

    from collections import Counter
    by_source: Counter = Counter()
    for flow in captured:
        catalog.add_flow(flow)
        by_source[flow.source] += 1
    labels = harvest_labels(html)
    catalog.add_page(PageObservation(
        url=url, html=html, text=plain_text(html), labels=labels,
    ))
    return {
        "flows": len(captured),
        "pages": 1,
        "labels": len(labels),
        "by_source": dict(by_source),
        "error": nav_error,
    }
