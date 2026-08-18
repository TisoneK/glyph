"""Live-capture CLI wiring — testable without Playwright installed.

The live browser run itself needs the `live` extra and a network target,
so it isn't unit-tested here; these cover the plumbing: subcommand
registration, the GLYPH_PROXY fallback, and graceful degradation when
Playwright is missing. The browse-mode tests inject a fake
``playwright.sync_api`` and so need the `live` extra installed — they skip
when it isn't.
"""
from __future__ import annotations

import importlib.util

import pytest

from glyph.cli import _live_kwargs, build_parser, main

_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None


def test_capture_live_registered_with_defaults():
    args = build_parser().parse_args(
        ["capture", "live", "https://x.test", "--db", "/tmp/x.db"])
    assert args.func.__name__ == "run_live"
    assert args.func.__module__.endswith("cli.capture")
    assert args.url == "https://x.test"
    assert args.explore == 2 and args.settle_ms == 3000 and args.timeout_ms == 30000


def test_run_live_registered():
    args = build_parser().parse_args(["run", "live", "https://y.test", "--explore", "5"])
    assert args.func.__name__ == "run_live"
    assert args.func.__module__.endswith("cli.run")
    assert args.explore == 5


def test_browser_and_target_short_aliases_are_accepted():
    args = build_parser().parse_args(
        ["run", "live", "-b", "brave", "-t", "google.com"])
    assert args.browser == "brave"
    assert args.target == "google.com"
    assert args.url is None
    assert _live_kwargs(args)["browse"] is True

    args = build_parser().parse_args(
        ["run", "live", "--browser", "brave", "--target", "google.com"])
    assert args.browser == "brave"
    assert args.target == "google.com"


def test_target_url_normalizes_explicit_and_positional_forms():
    from glyph.cli._shared import target_url
    args = build_parser().parse_args(["capture", "live", "--target", "google.com"])
    assert target_url(args) == "https://google.com"
    args = build_parser().parse_args(["capture", "live", "https://google.com"])
    assert target_url(args) == "https://google.com"


def test_proxy_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("GLYPH_PROXY", "http://env-proxy:8080")
    args = build_parser().parse_args(["capture", "live", "https://x.test"])
    assert _live_kwargs(args)["proxy"] == "http://env-proxy:8080"


def test_explicit_proxy_overrides_env(monkeypatch):
    monkeypatch.setenv("GLYPH_PROXY", "http://env-proxy:8080")
    args = build_parser().parse_args(
        ["capture", "live", "https://x.test", "--proxy", "http://flag:9090"])
    assert _live_kwargs(args)["proxy"] == "http://flag:9090"


@pytest.mark.skipif(_PLAYWRIGHT, reason="Playwright installed — can't test the missing-dep path")
def test_graceful_without_playwright(tmp_path, capsys):
    rc = main(["capture", "live", "https://x.invalid", "--db", str(tmp_path / "c.db")])
    assert rc == 1
    assert "Playwright" in capsys.readouterr().err


# --- Browse mode (ADR-14) -------------------------------------------------
#
# The browse path is unit-tested by injecting a fake `sync_playwright` whose
# CDP-attach / launch / page objects record what the driver did. No real
# browser is launched.


class _FakeEvent:
    """A minimal Playwright Event-emitter stand-in."""
    def __init__(self):
        self._handlers = {}

    def on(self, name, fn):
        self._handlers.setdefault(name, []).append(fn)


class _FakePage(_FakeEvent):
    def __init__(self):
        super().__init__()
        self.url = "about:blank"
        self.goto_calls = []
        self.content_calls = 0

    def goto(self, url, **kw):
        self.goto_calls.append((url, kw))
        self.url = url

    def content(self):
        self.content_calls += 1
        return "<html></html>"

    def wait_for_timeout(self, ms):
        pass


class _FakeContext(_FakeEvent):
    def __init__(self, browser=None, persistent=False):
        super().__init__()
        self.pages = []
        self.browser = browser
        self._persistent = persistent
        self.cookies_calls = 0

    def new_page(self):
        p = _FakePage()
        self.pages.append(p)
        return p

    def cookies(self):
        self.cookies_calls += 1
        return [{"name": "session", "value": "abc"}]


class _FakeBrowser(_FakeEvent):
    def __init__(self, contexts=None, via_cdp=False):
        super().__init__()
        self.contexts = contexts if contexts is not None else []
        self._via_cdp = via_cdp
        self.closed = False

    def new_context(self):
        c = _FakeContext(browser=self)
        self.contexts.append(c)
        return c

    def close(self):
        self.closed = True


class _FakeChromium:
    """Records connect_over_cdp / launch / launch_persistent_context calls."""
    def __init__(self, cdp_browser=None, cdp_raises=False):
        self.cdp_browser = cdp_browser
        self.cdp_raises = cdp_raises
        self.connect_calls = []
        self.launch_calls = []
        self.persistent_calls = []
        self._next_browser = _FakeBrowser()

    def connect_over_cdp(self, url):
        self.connect_calls.append(url)
        if self.cdp_raises:
            raise ConnectionError(f"no browser at {url}")
        return self.cdp_browser

    def launch(self, **kw):
        self.launch_calls.append(kw)
        b = _FakeBrowser()
        b.contexts.append(_FakeContext(browser=b))
        return b

    def launch_persistent_context(self, user_data_dir, **kw):
        self.persistent_calls.append((user_data_dir, kw))
        return _FakeContext(persistent=True)


class _FakePlaywrightCtx:
    def __init__(self, chromium):
        self.chromium = chromium

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakePlaywright:
    def __init__(self, chromium):
        self._chromium = chromium

    def __call__(self):
        return _FakePlaywrightCtx(self._chromium)


def _patch_playwright(monkeypatch, chromium):
    import playwright.sync_api as psa
    monkeypatch.setattr(psa, "sync_playwright", _FakePlaywright(chromium))


_BROWSE_SKIP = pytest.mark.skipif(
    not _PLAYWRIGHT,
    reason="browse tests patch the real playwright.sync_api module — install the live extra")


@_BROWSE_SKIP
def test_browse_attach_connects_and_hooks_target_tab(tmp_path, monkeypatch):
    """CDP-attach: connect_over_cdp called, a new tab opened + hooked, and
    a browser disconnect stops capture WITHOUT closing the user's browser
    (Ctrl+C detaches; here we fire the disconnect event the driver listens for)."""
    import glyph.capture.driver as drv
    from glyph.catalog import Catalog

    existing_context = _FakeContext()
    target_browser = _FakeBrowser(contexts=[existing_context], via_cdp=True)
    chromium = _FakeChromium(cdp_browser=target_browser, cdp_raises=False)
    _patch_playwright(monkeypatch, chromium)

    db = str(tmp_path / "b.db")
    cat = Catalog(db)
    # Fire the browser's "disconnected" handlers shortly after capture starts
    # (the driver registers one → sets `done` → the blocking wait returns).
    import threading as _t
    import time
    def _fire_disconnect():
        time.sleep(0.2)
        for fn in target_browser._handlers.get("disconnected", []):
            fn()
    _t.Thread(target=_fire_disconnect, daemon=True).start()

    res = drv.capture_url(cat, "https://target.test", browse=True,
                          progress=lambda m: None)
    cap_mode = cat.get_meta("capture_mode")
    cap_status = cat.get_meta("capture_status")
    stop_reason = cat.get_meta("capture_stop_reason")

    assert chromium.connect_calls == ["http://localhost:9222"]
    # A fresh tab was opened in the user's existing context (target tab).
    assert len(existing_context.pages) == 1
    assert existing_context.pages[0].goto_calls[0][0] == "https://target.test"
    # The target tab got the capture listeners (response/request/websocket/popup).
    hooked = set(existing_context.pages[0]._handlers.keys())
    assert {"response", "request", "websocket", "popup"}.issubset(hooked)
    # A disconnect in attach mode must NOT close the user's browser (the
    # driver only breaks its wait; it does not call browser.close()).
    assert target_browser.closed is False
    assert res["mode"] == "browse-attach"
    assert res["stop_reason"] == "browser_closed"
    assert cap_mode == "browse-attach"
    assert cap_status == "done"
    assert stop_reason == "browser_closed"
    cat.close()


@_BROWSE_SKIP
def test_browse_attach_stop_event_detaches_without_closing_browser(tmp_path, monkeypatch):
    """A TUI stop signal ends the worker and preserves the attached browser."""
    import glyph.capture.driver as drv
    from glyph.catalog import Catalog

    existing_context = _FakeContext()
    target_browser = _FakeBrowser(contexts=[existing_context], via_cdp=True)
    chromium = _FakeChromium(cdp_browser=target_browser, cdp_raises=False)
    _patch_playwright(monkeypatch, chromium)

    db = str(tmp_path / "stop.db")
    cat = Catalog(db)
    import threading as _t
    import time
    stop = _t.Event()

    def _request_stop():
        time.sleep(0.2)
        stop.set()

    _t.Thread(target=_request_stop, daemon=True).start()
    res = drv.capture_url(cat, "https://target.test", browse=True,
                          stop_event=stop, progress=lambda m: None)
    assert res["mode"] == "browse-attach"
    assert stop.is_set()
    assert target_browser.closed is False
    assert res["stop_reason"] == "user_stopped"
    assert cat.get_meta("capture_status") == "done"
    assert cat.get_meta("capture_stop_reason") == "user_stopped"
    cat.close()


@_BROWSE_SKIP
def test_browse_attach_all_traffic_hooks_every_tab(tmp_path, monkeypatch):
    """No url → all-traffic: every existing tab is hooked + context.on('page')."""
    import glyph.capture.driver as drv
    from glyph.catalog import Catalog

    existing = [_FakePage(), _FakePage()]  # two already-open tabs
    ec = _FakeContext()
    ec.pages = existing
    target_browser = _FakeBrowser(contexts=[ec], via_cdp=True)
    chromium = _FakeChromium(cdp_browser=target_browser, cdp_raises=False)
    _patch_playwright(monkeypatch, chromium)

    db = str(tmp_path / "b.db")
    cat = Catalog(db)
    import threading as _t
    import time
    def _fire_disconnect():
        time.sleep(0.2)
        for fn in target_browser._handlers.get("disconnected", []):
            fn()
    _t.Thread(target=_fire_disconnect, daemon=True).start()

    res = drv.capture_url(cat, None, browse=True, progress=lambda m: None)
    cat.close()

    # Both pre-existing tabs got hooked (response listener present).
    for p in existing:
        assert "response" in p._handlers
    # context.on("page", ...) registered (new-tab hook).
    assert "page" in ec._handlers
    # No new tab was opened (all-traffic reuses existing tabs).
    assert len(ec.pages) == 2
    assert res["mode"] == "browse-attach"


@_BROWSE_SKIP
def test_browse_launch_fallback_when_no_cdp(tmp_path, monkeypatch):
    """CDP-attach fails → launch_persistent_context fallback with channel."""
    import glyph.capture.driver as drv
    from glyph.catalog import Catalog

    chromium = _FakeChromium(cdp_browser=None, cdp_raises=True)
    _patch_playwright(monkeypatch, chromium)

    db = str(tmp_path / "b.db")
    cat = Catalog(db)
    import threading as _t
    import time
    # In the launch-fallback, browser_obj is context.browser (None for a
    # persistent context) → the driver watches context.on("close"). Fire it.
    fired = {"ctx": None}
    real_persistent = chromium.launch_persistent_context

    def _wrapped(user_data_dir, **kw):
        ctx = real_persistent(user_data_dir, **kw)
        fired["ctx"] = ctx
        return ctx
    chromium.launch_persistent_context = _wrapped

    def _fire_close():
        time.sleep(0.2)
        ctx = fired["ctx"]
        if ctx is not None:
            for fn in ctx._handlers.get("close", []):
                fn()
    _t.Thread(target=_fire_close, daemon=True).start()

    res = drv.capture_url(cat, "https://target.test", browse=True,
                          browser="chrome", progress=lambda m: None)
    cap_mode = cat.get_meta("capture_mode")
    cat.close()

    assert chromium.connect_calls == ["http://localhost:9222"]  # tried CDP first
    assert len(chromium.persistent_calls) == 1  # fell back to launch
    profile, kw = chromium.persistent_calls[0]
    assert kw["headless"] is False
    assert kw["channel"] == "chrome"
    assert isinstance(kw["chromium_sandbox"], bool)
    assert profile.endswith("target.test")
    assert res["mode"] == "browse-launch"
    assert cap_mode == "browse-launch"


@_BROWSE_SKIP
def test_browse_launch_brave_needs_path_or_autodetect(tmp_path, monkeypatch):
    """Brave has no channel=; without a binary it raises a clear error."""
    import glyph.capture.driver as drv
    from glyph.catalog import Catalog

    chromium = _FakeChromium(cdp_browser=None, cdp_raises=True)
    _patch_playwright(monkeypatch, chromium)
    # No brave binary on this sandbox → auto-detect returns None.
    monkeypatch.setattr(drv, "_browser_binary_path", lambda b: None)

    db = str(tmp_path / "b.db")
    cat = Catalog(db)
    with pytest.raises(RuntimeError, match="Brave"):
        drv.capture_url(cat, "https://x.test", browse=True, browser="brave",
                        progress=lambda m: None)
    cat.close()


def test_browse_flags_in_parser():
    """--browse and friends are registered on the live subcommands."""
    for cmd in (["capture", "live", "https://x.test", "--browse"],
                ["run", "live", "https://x.test", "--browse", "--browser", "brave"]):
        args = build_parser().parse_args(cmd)
        assert args.browse is True
        assert args.cdp_port == 9222
        assert args.cdp_host == "localhost"
        assert args.browser in ("chrome", "brave")
    # url is now optional (nargs='?')
    args = build_parser().parse_args(["capture", "live", "--browse"])
    assert args.url is None
    assert args.browse is True


def test_browser_option_is_a_real_browser_mode_alias():
    """The requested ``--browser`` spelling enables continuous real-browser
    capture, while still accepting a browser name for launch fallback.

    The URL is positional before the flag when both are supplied; omitting it
    intentionally selects all-traffic mode over the user's existing tabs.
    """
    args = build_parser().parse_args(
        ["run", "live", "https://target.test", "--browser"])
    assert args.browser == "chrome"
    assert args.browser_requested is True
    assert args.url == "https://target.test"
    kw = _live_kwargs(args)
    assert kw["browse"] is True
    assert kw["cdp_url"] == "http://localhost:9222"

    args = build_parser().parse_args(
        ["capture", "live", "https://target.test", "--browser", "brave"])
    assert args.browser == "brave"
    assert args.browser_requested is True
    assert args.url == "https://target.test"


def test_browser_option_without_url_enables_all_traffic():
    args = build_parser().parse_args(["capture", "live", "--browser"])
    assert args.url is None
    assert args.browser_requested is True
    assert _live_kwargs(args)["browse"] is True


def test_live_kwargs_carries_browse_options(monkeypatch):
    args = build_parser().parse_args(
        ["capture", "live", "--browse", "--cdp-port", "9333",
         "--browser", "brave", "--incognito"])
    kw = _live_kwargs(args)
    assert kw["browse"] is True
    assert kw["cdp_url"] == "http://localhost:9333"
    assert kw["browser"] == "brave"
    assert kw["incognito"] is True
    # GLYPH_CDP_URL env overrides the host:port construction.
    monkeypatch.setenv("GLYPH_CDP_URL", "http://remote:9222")
    args2 = build_parser().parse_args(["capture", "live", "--browse"])
    assert _live_kwargs(args2)["cdp_url"] == "http://remote:9222"


def test_geo_block_classifier_is_conservative():
    from glyph.capture.driver import _geo_block_reason
    assert _geo_block_reason(451, "")
    assert _geo_block_reason(403, "This service is not available in your country")
    assert _geo_block_reason(error="net::ERR_NETWORK_ACCESS_DENIED")
    assert _geo_block_reason(403, "Access denied") is None


def test_explicit_browser_path_and_profile_enable_browse_mode(monkeypatch):
    monkeypatch.setenv("GLYPH_BROWSER_PATH", "/opt/custom/chrome")
    monkeypatch.setenv("GLYPH_BROWSER_PROFILE", "/tmp/glyph-profile")
    args = build_parser().parse_args(["capture", "live", "https://target.test"])
    kw = _live_kwargs(args)
    assert kw["browse"] is True  # environment configuration enables browse mode
    assert kw["browser_path"] == "/opt/custom/chrome"
    assert kw["user_data_dir"] == "/tmp/glyph-profile"
    assert kw["force_launch"] is True

    args = build_parser().parse_args([
        "capture", "live", "https://target.test",
        "--browser-path", "/custom/brave", "--user-data-dir", "/custom/profile"])
    kw = _live_kwargs(args)
    assert kw["browse"] is True
    assert kw["browser_path"] == "/custom/brave"
    assert kw["user_data_dir"] == "/custom/profile"
    assert kw["force_launch"] is True


def test_browse_command_registered():
    """glyph browse --launch is a registered command."""
    args = build_parser().parse_args(["browse", "--launch", "--browser", "brave"])
    assert args.func.__module__.endswith("cli.browse")
    assert args.launch is True
    assert args.browser == "brave"


def test_auto_mode_still_requires_url(tmp_path, capsys):
    """Non-browse auto path: no url → clear error, not a crash."""
    rc = main(["capture", "live", "--db", str(tmp_path / "c.db")])
    assert rc == 1
    assert "URL" in capsys.readouterr().err or "browse" in capsys.readouterr().err
