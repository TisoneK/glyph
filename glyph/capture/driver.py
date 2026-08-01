"""Playwright driver — drive a URL and capture API + DOM (optional backend).

Requires the ``live`` extra (``pip install glyph-re[live]`` plus
``playwright install chromium``). Imports cleanly without Playwright; the
dependency is checked only when :func:`capture_url` is called.

Two capture modes (ADR-14):

- **Auto** (default): headless Chromium, ``page.goto(url)``, settle, then
  ``explore`` target-agnostic interaction rounds (scroll + generic clicks).
  Returns when the rounds finish. Used by ``glyph run live``/``capture live``
  without ``--browse``.
- **Browse** (``browse=True``): a VISIBLE browser the USER drives. Primary
  path = CDP-attach to the user's real browser (Brave/Edge/Chrome) launched
  with ``--remote-debugging-port=9222``; fallback = Playwright launches the
  real-browser binary with a dedicated profile. Capture hooks the target tab
  (+ popups) and blocks until Ctrl+C (detach) or the browser closes — so
  auth/payment/login/deposit/withdrawal flows the auto-explore path misses
  get captured. If ``url`` is omitted, all-traffic mode hooks every tab.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Optional
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


def _browser_binary_path(browser: str) -> Optional[str]:
    """Resolve a real-browser binary path for the launch fallback (Brave only).

    Playwright natively supports ``channel="chrome"`` and ``channel="msedge"``
    but has NO ``channel="brave"`` — so for Brave we must pass ``executable_path``
    to the binary. Returns the first existing candidate, or ``None`` if not found
    (caller then raises a clear error). Per ADR-14 point 2.
    """
    if browser != "brave":
        return None  # chrome/edge use channel=, no path needed
    candidates = {
        "darwin": [
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ],
        "linux": [
            "/usr/bin/brave-browser", "/usr/bin/brave",
            "/snap/bin/brave",
        ],
        "win32": [
            os.path.join(os.environ.get("ProgramFiles", ""),
                         "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""),
                         "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        ],
    }.get(_platform_key(), [])
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _platform_key() -> str:
    import platform
    s = platform.system().lower()
    if s == "darwin":
        return "darwin"
    if s.startswith("win"):
        return "win32"
    return "linux"


def _chromium_sandbox_enabled() -> bool:
    """Use Chromium's sandbox whenever the host permits it.

    Playwright disables the sandbox by default in some versions, which makes
    Chromium print its ``--no-sandbox`` warning even though Glyph never adds
    that flag itself.  A root Linux process cannot use the sandbox; retain the
    compatibility fallback there, while enabling it on normal macOS, Windows,
    and non-root Linux installations.
    """
    if _platform_key() == "linux":
        try:
            return os.geteuid() != 0
        except AttributeError:  # pragma: no cover - Windows has no geteuid
            pass
    return True


def _make_recorders(catalog: Catalog, by_source, state, url: Optional[str],
                    snapshot: bool = True):
    """Build the response/request/websocket handlers + a page-hook installer.

    Shared by the auto and browse modes so the capture semantics are identical.
    Returns ``(hook_page, record)`` where ``hook_page(page)`` registers every
    relevant listener on a Playwright ``Page`` (and recursively on its popups),
    and ``record(flow)`` persists a flow + bumps the by_source counter.

    ``snapshot`` — in auto mode the single page_observations row is replaced on
    each snapshot; in browse mode we snapshot the target tab on navigation but
    skip snapshots for popups/all-traffic tabs (their DOM is transient).
    """
    def record(flow: Flow) -> None:
        catalog.add_flow(flow)
        by_source[flow.source] += 1

    def _snapshot(page) -> None:
        if not snapshot:
            return
        try:
            html = page.content()
        except Exception:
            return
        labels = harvest_labels(html)
        # Replace the single page_observations row (the DOM is cumulative).
        catalog.conn.execute("DELETE FROM page_observations")
        catalog.add_page(PageObservation(
            url=(url or page.url or ""), html=html,
            text=plain_text(html), labels=labels))
        state["labels"] = len(labels)

    def on_response(response) -> None:
        req = response.request
        rtype = req.resource_type or "unknown"
        try:
            body = response.text()
        except Exception:
            body = None
        record(Flow(
            method=req.method, url=response.url, host="", path="",
            req_headers=dict(req.headers), status=response.status,
            resp_headers=dict(response.headers), resp_body=body,
            resp_mime=(response.headers.get("content-type") or "")
            .split(";")[0] or None,
            source=f"playwright:{rtype}"))

    def on_request(req) -> None:
        # Additive (ADR-14 point 1): captures the request side, including
        # requests whose responses never arrive (cancelled, preflight-rejected,
        # beacon fire-and-forget). No response body / status here.
        rtype = req.resource_type or "unknown"
        try:
            rbody = req.post_data
        except Exception:
            rbody = None
        record(Flow(
            method=req.method, url=req.url, host="", path="",
            req_headers=dict(req.headers), req_body=rbody,
            status=0, resp_headers={}, resp_body=None,
            resp_mime=(req.headers.get("content-type") or "").split(";")[0] or None,
            source=f"playwright:request:{rtype}"))

    def on_websocket(ws) -> None:
        ws_url = getattr(ws, "url", "")

        def sent(payload, *a, **kw):
            record(Flow(
                method="WS_SEND", url=ws_url, host="", path="", query="",
                req_headers={},
                req_body=payload if isinstance(payload, str) else None,
                status=0, resp_headers={}, resp_body=None,
                resp_mime="websocket", source="playwright:websocket"))

        def recv(payload, *a, **kw):
            record(Flow(
                method="WS_RECV", url=ws_url, host="", path="", query="",
                req_headers={}, req_body=None,
                resp_body=payload if isinstance(payload, str) else None,
                status=0, resp_headers={},
                resp_mime="websocket", source="playwright:websocket"))

        try:
            ws.on("framesent", sent)
            ws.on("framereceived", recv)
        except Exception:
            pass

    hooked_pages = set()

    def hook_page(page) -> None:
        """Register every capture listener once on a Page.

        A popup can be reported by both a page-level ``popup`` event and the
        context-level ``page`` event in all-tabs mode. Identity-based
        de-duplication keeps those two lineage paths from recording flows
        twice.
        """
        key = id(page)
        if key in hooked_pages:
            return
        hooked_pages.add(key)
        try:
            page.on("response", on_response)
        except Exception:
            pass
        try:
            page.on("request", on_request)
        except Exception:
            pass
        try:
            page.on("websocket", on_websocket)
        except Exception:
            pass
        try:
            page.on("popup", hook_page)  # new tabs FROM this tab → hooked too
        except Exception:
            pass

    return hook_page, record, _snapshot


def capture_url(catalog: Catalog, url: Optional[str] = None,
                wait_selector: Optional[str] = None,
                timeout_ms: int = 15000,
                proxy: Optional[str] = None,
                settle_ms: int = 3000,
                explore: int = 0,
                *,
                browse: bool = False,
                cdp_url: Optional[str] = None,
                browser: str = "chrome",
                user_data_dir: Optional[str] = None,
                incognito: bool = False,
                browser_path: Optional[str] = None,
                stop_event: Optional[threading.Event] = None,
                progress=None) -> dict:
    """Capture a target's traffic into the catalog.

    Two modes (ADR-14):

    - **Auto** (``browse=False``, the default): load ``url`` headless, settle,
      run ``explore`` target-agnostic interaction rounds, return. ``url`` is
      required.
    - **Browse** (``browse=True``): a VISIBLE browser the user drives. PRIMARY
      = CDP-attach to the user's real browser (Brave/Edge/Chrome) on
      ``--remote-debugging-port=9222``; FALLBACK = Playwright launches the
      real-browser binary with a dedicated profile. Hooks the target tab +
      popups (or every tab if ``url`` is None — all-traffic). Blocks until
      Ctrl+C (attach: detach, browser stays open) or the browser closes. So
      auth/payment/login/deposit/withdrawal flows the auto path misses get
      captured. ``url`` is optional in browse mode.

    Raises :class:`RuntimeError` with install guidance if Playwright is missing.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised only with extra
        raise RuntimeError(
            "Playwright is not installed. Install the live extra:\n"
            "  pip install 'glyph-re[live]' && playwright install chromium"
        ) from exc

    if browse:
        return _capture_browse(
            catalog, url, sync_playwright,
            cdp_url=cdp_url, browser=browser, user_data_dir=user_data_dir,
            incognito=incognito, browser_path=browser_path,
            stop_event=stop_event, timeout_ms=timeout_ms, progress=progress)

    if not url:
        raise RuntimeError("a target URL is required for auto (non-browse) capture")

    from collections import Counter
    catalog.set_target(urlparse(url).hostname)  # anchors first/third-party
    catalog.set_meta("capture_status", "running")
    catalog.set_meta("capture_mode", "auto")
    catalog.set_meta("capture_started", str(time.time()))
    by_source: Counter = Counter()
    state = {"labels": 0}
    launch_kwargs = {
        "headless": True,
        "chromium_sandbox": _chromium_sandbox_enabled(),
    }
    if proxy:
        launch_kwargs["proxy"] = _parse_proxy(proxy)

    hook_page, _record, _snapshot = _make_recorders(
        catalog, by_source, state, url, snapshot=True)

    nav_error: Optional[str] = None
    try:
        with sync_playwright() as pw:
            browser_obj = pw.chromium.launch(**launch_kwargs)
            page = browser_obj.new_page()
            hook_page(page)

            # domcontentloaded milestone, then settle + explore; best-effort so
            # a nav failure never discards what was already captured.
            try:
                if progress:
                    progress(f"loading {url}…")
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
                    if progress:
                        progress(f"page loaded — settling {settle_ms}ms for late XHR…")
                    page.wait_for_timeout(settle_ms)
                _snapshot(page)
                for i in range(max(0, explore)):
                    if progress:
                        progress(f"explore round {i + 1}/{explore}…")
                    _explore_round(page, timeout_ms)
                    _snapshot(page)
            except Exception as exc:
                nav_error = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            try:
                _snapshot(page)
            except Exception:
                pass
            browser_obj.close()
    finally:
        # Persist the same error that the headless result returns. The live
        # TUI reads metadata from a separate connection, so returning a dict
        # alone would make a failed Windows navigation look like success.
        catalog.set_meta("capture_status", "done")
        catalog.set_meta("capture_error", nav_error or "")

    return {
        "flows": sum(by_source.values()),
        "pages": 1,
        "labels": state["labels"],
        "by_source": dict(by_source),
        "error": nav_error,
        "mode": "auto",
    }


def _capture_browse(catalog: Catalog, url: Optional[str], sync_playwright, *,
                    cdp_url: Optional[str], browser: str,
                    user_data_dir: Optional[str], incognito: bool,
                    browser_path: Optional[str],
                    stop_event: Optional[threading.Event], timeout_ms: int,
                    progress=None) -> dict:
    """Browse mode — CDP-attach primary, launch fallback (ADR-14)."""
    from collections import Counter
    import sys

    def _say(msg: str) -> None:
        if progress:
            progress(msg)
        else:
            print(f"  {msg}", file=sys.stderr, flush=True)

    # Target host (if given) — ADR-12: activate + clear this target's old rows.
    host = urlparse(url).hostname if url else None
    if host:
        catalog.set_target(host)
        catalog.clear_target()
    else:
        # All-tabs mode has no canonical host. Clear the persisted target so
        # writes land in the reserved unassigned bucket and display readers
        # intentionally show the complete live session rather than silently
        # hiding it under the last previously processed target.
        catalog.clear_active_target()
    catalog.set_meta("capture_status", "running")
    catalog.set_meta("capture_started", str(time.time()))
    catalog.set_meta("capture_stop_reason", "")
    by_source: Counter = Counter()
    state = {"labels": 0}

    # In browse mode we snapshot only the target tab (skip popups/all-traffic
    # tabs — their DOM is transient). When no url (all-traffic), skip snapshots
    # entirely (no single canonical page to track).
    hook_page, _record, _snapshot = _make_recorders(
        catalog, by_source, state, url, snapshot=bool(url))

    cdp_target = cdp_url or os.environ.get("GLYPH_CDP_URL") or "http://localhost:9222"
    mode: str
    nav_error: Optional[str] = None
    done = threading.Event()
    stop_reason = "error"

    def _snapshot_cookies(ctx) -> None:
        """context.cookies() snapshot — document.cookie reads are invisible to
        the response hook (ADR-14 point 1). v1: JSON blob in meta. MUST run on
        the main thread: Playwright's sync API is NOT thread-safe (its objects
        are greenlet-bound to the thread that created them; calling ctx.cookies()
        from a daemon thread corrupts the greenlet state and floods shutdown
        with 'cannot switch to a different thread' + TargetClosedError)."""
        if ctx is None:
            return
        try:
            catalog.set_meta("capture_cookies", json.dumps(ctx.cookies()))
        except Exception:
            pass  # context closing/closed — best-effort

    try:
        with sync_playwright() as pw:
            browser_obj = None
            context = None
            attached_browser = False
            owns_browser = False
            # --- PRIMARY: CDP-attach to the user's real browser ---------------
            try:
                browser_obj = pw.chromium.connect_over_cdp(cdp_target)
                attached_browser = True
                mode = "browse-attach"
                # The user's existing context holds their session (cookies,
                # saved logins, password manager). Reuse it; don't make a new
                # isolated context or none of their logins carry over.
                contexts = browser_obj.contexts
                context = contexts[0] if contexts else browser_obj.new_context()
            except Exception as exc:
                # --- FALLBACK: launch the real-browser binary -----------------
                _say(f"no browser on {cdp_target} ({exc.__class__.__name__}) "
                     f"— launching {browser} with a dedicated profile…")
                launch_kwargs: dict = {
                    "headless": False,
                    "chromium_sandbox": _chromium_sandbox_enabled(),
                }
                if browser_path:
                    # An explicit path always wins, regardless of the friendly
                    # browser name. This is the portable escape hatch for
                    # custom Chrome/Chromium/Brave installations.
                    launch_kwargs["executable_path"] = browser_path
                elif browser in ("chrome", "msedge"):
                    launch_kwargs["channel"] = browser
                elif browser == "brave":
                    path = _browser_binary_path("brave")
                    if not path:
                        raise RuntimeError(
                            "Could not find the Brave binary. Pass --browser-path "
                            "/path/to/brave, or use --browser chrome|msedge.")
                    launch_kwargs["executable_path"] = path
                profile = user_data_dir or os.path.expanduser(
                    f"~/.glyph/profiles/{host or 'default'}")
                os.makedirs(profile, exist_ok=True)
                if incognito:
                    browser_obj = pw.chromium.launch(**launch_kwargs)
                    context = browser_obj.new_context()
                else:
                    context = pw.chromium.launch_persistent_context(
                        user_data_dir=profile, **launch_kwargs)
                    browser_obj = context.browser  # may be None for persistent
                owns_browser = True
                mode = "browse-launch"

            catalog.set_meta("capture_mode", mode)
            catalog.set_meta("capture_stop_reason", "")
            if not _chromium_sandbox_enabled():
                _say("warning: Chromium sandbox is unavailable for this root Linux process; "
                     "the browser may display a --no-sandbox warning")

            # A persistent profile can restore its last visible page. For a
            # target-scoped launch, close those owned stale pages before
            # opening the requested target. Never touch existing pages in CDP
            # attach mode: those belong to the user's real browser session.
            if owns_browser and url:
                for old_page in list(context.pages):
                    try:
                        old_page.close()
                    except Exception:
                        pass

            # --- hook pages per the capture-scoping rule (ADR-14 point 7) ----
            if url:
                # Default: target tab + popups only. Existing/other tabs NOT
                # hooked → the user's email/social/other-banking tabs invisible.
                target_page = context.new_page()
                hook_page(target_page)
                try:
                    target_page.goto(url, timeout=timeout_ms,
                                     wait_until="domcontentloaded")
                except Exception as exc:
                    nav_error = (str(exc).splitlines()[0] if str(exc)
                                 else type(exc).__name__)
                # Snapshot the target tab now + on each navigation (Rosetta DOM).
                try:
                    _snapshot(target_page)
                    target_page.on("framenavigated",
                                   lambda f: _snapshot(f.frame().page)
                                   if getattr(f, "is_main_frame", lambda: False)()
                                   else None)
                except Exception:
                    pass
                _say(f"[{mode}] attached — navigate, log in, do your flows.")
                _say("Ctrl+C here when done"
                     + (" (browser stays open)." if mode == "browse-attach"
                        else " or close the browser."))
            else:
                # All-traffic fallback (no target url): hook EVERY tab.
                _say(f"[{mode}] ⚠ browse-all mode: capturing EVERY tab in your "
                     f"browser (email, social, other-banking — everything). "
                     f"Ctrl+C to stop.")
                for p in context.pages:
                    hook_page(p)
                try:
                    # In all-traffic mode context.page is the sole source of
                    # new-tab events; popup listeners would hook the same page
                    # twice and duplicate every recorded flow.
                    context.on("page", hook_page)
                except Exception:
                    pass

            # --- block until Ctrl+C or the browser disconnects ---------------
            # Poll with a short timeout (not a bare done.wait()) so Ctrl+C /
            # KeyboardInterrupt is delivered promptly — a C-level indefinite
            # wait can swallow the signal on some Python builds. The periodic
            # cookie snapshot runs INLINE here on the main thread (every ~5s);
            # a daemon thread would call Playwright's sync API cross-thread,
            # which is unsafe and floods shutdown with greenlet errors.
            stop_reason = "completed"

            def _live_page():
                for candidate in list(getattr(context, "pages", []) or []):
                    try:
                        if not candidate.is_closed():
                            return candidate
                    except Exception:
                        return candidate
                return None

            def _browser_closed() -> None:
                nonlocal stop_reason
                # A requested stop may close the owned context as part of
                # cleanup. Preserve the more useful user-stopped reason rather
                # than reporting that deliberate close as an external close.
                if stop_event is None or not stop_event.is_set():
                    stop_reason = "browser_closed"
                done.set()

            try:
                if browser_obj is not None:
                    try:
                        browser_obj.on("disconnected", _browser_closed)
                    except Exception:
                        pass
                # Watch the context as well as the Browser. Persistent
                # contexts expose ``context.browser`` differently across
                # Playwright versions; context close is the stable signal for
                # a user closing a Glyph-owned launch-fallback browser.
                if context is not None:
                    try:
                        context.on("close", _browser_closed)
                    except Exception:
                        pass
                _last_cookie_snap = 0.0
                while not done.is_set():
                    # Sync Playwright dispatches browser events while one of
                    # its own API calls is running. A bare threading.Event
                    # wait does not pump that loop, so responses and browser
                    # close notifications could appear to stop arriving.
                    # BrowserContext has no wait_for_timeout on every
                    # Playwright version, so pump a live Page instead.
                    pump_page = _live_page()
                    try:
                        if pump_page is not None:
                            pump_page.wait_for_timeout(200)
                        elif context is not None:
                            # Keep the sync Playwright dispatcher alive after
                            # the final tab closes. `time.sleep` alone would
                            # delay BrowserContext.close/disconnect callbacks.
                            context.cookies()
                            time.sleep(0.2)
                        else:  # lightweight fake compatibility
                            time.sleep(0.2)
                    except Exception:
                        if stop_event is not None and stop_event.is_set():
                            stop_reason = "user_stopped"
                        else:
                            stop_reason = "browser_closed"
                        done.set()
                        break
                    # Textual workers do not receive KeyboardInterrupt. The
                    # caller therefore supplies an Event for an explicit,
                    # thread-safe stop (TUI Stop / graceful app shutdown).
                    if stop_event is not None and stop_event.is_set():
                        stop_reason = "user_stopped"
                        done.set()
                        break
                    now = time.time()
                    if now - _last_cookie_snap >= 5.0:
                        _snapshot_cookies(context)
                        _last_cookie_snap = now
                if stop_event is not None and stop_event.is_set():
                    stop_reason = "user_stopped"
                    if attached_browser:
                        _say("stop requested — detaching (browser stays open)…")
                    elif owns_browser:
                        _say("stop requested — closing browser…")
                        try:
                            if context is not None:
                                context.close()
                        except Exception:
                            pass
                        # Incognito launch uses a separate Browser object;
                        # persistent contexts are fully closed above.
                        if browser_obj is not None:
                            try:
                                browser_obj.close()
                            except Exception:
                                pass
            except KeyboardInterrupt:
                stop_reason = "interrupted"
                done.set()  # stop the poll loop first; no more cookie snaps
                if attached_browser:
                    _say("Ctrl+C — detaching (browser stays open)…")
                    # Do NOT close the attached browser or context: the user's
                    # real browser and all of its tabs remain usable.
                else:
                    _say("Ctrl+C — closing browser…")
                    try:
                        if context is not None:
                            context.close()
                    except Exception:
                        pass  # greenlet noise during shutdown — already done
                    if browser_obj is not None:
                        try:
                            browser_obj.close()
                        except Exception:
                            pass
            finally:
                _snapshot_cookies(context)  # final cookie snapshot (main thread)
    finally:
        done.set()
        catalog.set_meta("capture_status", "done")
        catalog.set_meta("capture_error", nav_error or "")
        catalog.set_meta("capture_stop_reason", locals().get("stop_reason", "error"))

    return {
        "flows": sum(by_source.values()),
        "pages": 1,
        "labels": state["labels"],
        "by_source": dict(by_source),
        "error": nav_error,
        "mode": mode,
        "stop_reason": stop_reason,
    }
