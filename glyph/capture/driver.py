"""Playwright driver — drive a URL and capture API + DOM (optional backend).

Requires the ``live`` extra (``pip install glyph-re[live]`` plus
``playwright install chromium``). Imports cleanly without Playwright; the
dependency is checked only when :func:`capture_url` is called.
"""
from __future__ import annotations

import time
from typing import Optional
from urllib.parse import unquote, urlparse

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

    from collections import Counter
    catalog.set_target(urlparse(url).hostname)  # anchors first/third-party
    catalog.set_meta("capture_status", "running")
    catalog.set_meta("capture_started", str(time.time()))
    by_source: Counter = Counter()
    state = {"labels": 0}
    launch_kwargs = {"headless": True}
    if proxy:
        launch_kwargs["proxy"] = _parse_proxy(proxy)

    def _record(flow: Flow) -> None:
        # Write each flow the moment it's seen so the live dashboard shows it
        # in real time (Phase 2), and so a crash never loses captured data.
        catalog.add_flow(flow)
        by_source[flow.source] += 1

    def _snapshot(page) -> None:
        # The browser DOM is cumulative, so replace the single snapshot each
        # time — DOM label counts grow live as the page renders/interacts.
        try:
            html = page.content()
        except Exception:
            return
        labels = harvest_labels(html)
        catalog.conn.execute("DELETE FROM page_observations")
        catalog.add_page(PageObservation(
            url=url, html=html, text=plain_text(html), labels=labels))
        state["labels"] = len(labels)

    nav_error: Optional[str] = None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_kwargs)
            page = browser.new_page()

            def on_response(response) -> None:
                # Capture EVERYTHING that moves (any resource type) — sites
                # hide API calls behind non-xhr types. The resource type is
                # preserved in `source` as "playwright:<type>".
                req = response.request
                rtype = req.resource_type or "unknown"
                try:
                    body = response.text()
                except Exception:
                    body = None  # binary body: metadata only
                _record(Flow(
                    method=req.method, url=response.url, host="", path="",
                    req_headers=dict(req.headers), status=response.status,
                    resp_headers=dict(response.headers), resp_body=body,
                    resp_mime=(response.headers.get("content-type") or "")
                    .split(";")[0] or None,
                    source=f"playwright:{rtype}"))

            page.on("response", on_response)

            def on_websocket(ws) -> None:
                ws_url = getattr(ws, "url", "")

                def sent(payload, *a, **kw):
                    _record(Flow(
                        method="WS_SEND", url=ws_url, host="", path="", query="",
                        req_headers={},
                        req_body=payload if isinstance(payload, str) else None,
                        status=0, resp_headers={}, resp_body=None,
                        resp_mime="websocket", source="playwright:websocket"))

                def recv(payload, *a, **kw):
                    _record(Flow(
                        method="WS_RECV", url=ws_url, host="", path="", query="",
                        req_headers={}, req_body=None,
                        resp_body=payload if isinstance(payload, str) else None,
                        status=0, resp_headers={},
                        resp_mime="websocket", source="playwright:websocket"))

                try:
                    ws.on("framesent", sent)
                    ws.on("framereceived", recv)
                except Exception:
                    pass  # older Playwright APIs differ; best-effort

            try:
                page.on("websocket", on_websocket)
            except Exception:
                pass  # websocket event not available in this Playwright version

            # domcontentloaded milestone, then settle + explore; best-effort so
            # a nav failure never discards what was already captured.
            try:
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=timeout_ms)
                    except Exception:
                        pass
                else:
                    try:
                        page.wait_for_load_state("load", timeout=timeout_ms)
                    except Exception:
                        pass
                if settle_ms > 0:
                    page.wait_for_timeout(settle_ms)
                _snapshot(page)
                for _ in range(max(0, explore)):
                    _explore_round(page, timeout_ms)
                    _snapshot(page)
            except Exception as exc:
                nav_error = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            try:
                _snapshot(page)
            except Exception:
                pass
            browser.close()
    finally:
        catalog.set_meta("capture_status", "done")

    return {
        "flows": sum(by_source.values()),
        "pages": 1,
        "labels": state["labels"],
        "by_source": dict(by_source),
        "error": nav_error,
    }
