"""TUI data adapters + dashboard/flows/dom CLI wiring.

The Textual app itself is smoke-tested via its async test harness; the data
adapters (the real logic) are pure and covered directly.
"""
from __future__ import annotations

import base64
import json

from glyph.capture import ingest_har
from glyph.catalog import Catalog
from glyph.cli import main
from glyph.rosetta import build_dictionary
from glyph.schema import infer_all
from glyph.tui import data as D


def _catalog(tmp_path, make_entry):
    db = str(tmp_path / "c.db")
    har = tmp_path / "s.har"
    har.write_text(json.dumps({"log": {"entries": [
        make_entry("POST", "https://shop.ke/api/login?token=eyJa.eyJb.cccccccccccc",
                   resp_headers={"Content-Length": "184000"},
                   body=json.dumps({"orders": [{"status": 3, "status_label": "Shipped"}],
                                    "user": {"email": "a@shop.ke"}})),
        make_entry("GET", "https://shop.ke/home", mime="text/html",
                   body="<button type=submit>Log In</button>"),
    ]}}))
    from glyph.sensitive import run_scan
    cat = Catalog(db)
    ingest_har(cat, str(har))
    infer_all(cat)
    build_dictionary(cat)
    run_scan(cat)  # populate findings (as `run live` does)
    return cat, db


def test_human_size():
    assert D.human_size(0) == "—"
    assert D.human_size(512) == "512 B"
    assert D.human_size(184000) == "180 KB"
    assert D.human_size(2 * 1024 ** 2) == "2.0 MB"


def test_flow_type_from_mime():
    from glyph.catalog import Flow
    assert D.flow_type(Flow(method="GET", url="x", host="", path="",
                            source="playwright:xhr")) == "xhr"
    assert D.flow_type(Flow(method="GET", url="x", host="", path="",
                            source="har", resp_mime="text/html")) == "document"


def test_endpoint_data_rows_classify_payloads_and_headers(tmp_path):
    """The Data tab exposes body-bearing endpoints, including binary bodies."""
    from glyph.catalog import Flow

    db = str(tmp_path / "data.db")
    cat = Catalog(db)
    cat.set_target("data.example")
    cat.add_flow(Flow(
        method="GET", url="https://data.example/api/items", host="", path="",
        status=200, resp_mime="application/json",
        resp_headers={"Content-Type": "application/json", "X-Trace": "json"},
        resp_body='{"items":[1,2]}'))
    cat.add_flow(Flow(
        method="GET", url="https://data.example/archive", host="", path="",
        status=200, resp_mime="application/octet-stream",
        resp_headers={"Content-Encoding": "gzip", "Content-Length": "4096"},
        resp_body=base64.b64encode(b"\x1f\x8bcompressed").decode("ascii")))
    cat.add_flow(Flow(
        method="GET", url="https://data.example/file.zip", host="", path="",
        status=200, resp_mime="application/octet-stream",
        resp_headers={"Content-Type": "application/zip"},
        resp_body=base64.b64encode(b"PK\x03\x04archive").decode("ascii")))
    # A request-only observation must not appear in Data.
    cat.add_flow(Flow(
        method="GET", url="https://data.example/ping", host="", path="",
        status=0, resp_mime=None, resp_body=None))

    headers, rows = D.endpoint_data_rows(cat)
    cat.close()

    assert headers == ["#", "METHOD", "ENDPOINT", "TYPE", "ENCODING",
                       "SIZE", "STATUS", "HEADERS", "DATA"]
    assert len(rows) == 3
    by_endpoint = {row[2]: row for row in rows}
    assert by_endpoint["data.example/api/items"][3] == "json"
    assert "X-Trace" in by_endpoint["data.example/api/items"][7]
    assert by_endpoint["data.example/archive"][3] == "gzip"
    assert by_endpoint["data.example/archive"][4] == "gzip"
    assert by_endpoint["data.example/archive"][5] == "4 KB"
    assert by_endpoint["data.example/file.zip"][3] == "zip"


def test_summary_counts(tmp_path, make_entry):
    cat, _ = _catalog(tmp_path, make_entry)
    s = D.summary(cat)
    assert s["flows"] == 2
    assert s["fields"] > 0
    assert s["dom_labels"] >= 1
    assert s["findings"] >= 1  # email + jwt in the login response
    cat.close()


def test_flow_rows_and_detail(tmp_path, make_entry):
    cat, _ = _catalog(tmp_path, make_entry)
    headers, rows = D.flow_rows(cat)
    assert headers[0] == "#" and headers[-1] == "URL"
    assert len(rows) == 2
    # size comes from Content-Length when present
    assert any("180 KB" in r[4] for r in rows)
    fid = int(rows[0][0])
    detail = D.flow_detail(cat, fid)
    assert detail and detail["method"] in ("POST", "GET")
    cat.close()


def test_filter(tmp_path, make_entry):
    cat, _ = _catalog(tmp_path, make_entry)
    _, rows = D.flow_rows(cat, text_filter="home")
    assert len(rows) == 1
    cat.close()


def test_view_adapters_nonempty(tmp_path, make_entry):
    cat, _ = _catalog(tmp_path, make_entry)
    for fn in (D.dom_rows, D.schema_rows, D.sensitive_rows, D.rosetta_rows):
        headers, rows = fn(cat)
        assert headers and isinstance(rows, list)
    cat.close()


def test_cli_flows_and_dom(tmp_path, make_entry, capsys):
    cat, db = _catalog(tmp_path, make_entry)
    cat.close()
    assert main(["flows", "--db", db]) == 0
    assert main(["dom", "--db", db]) == 0
    assert main(["flows", "--db", db, "--json"]) == 0
    out = capsys.readouterr().out
    assert "METHOD" in out or "method" in out.lower()


def test_catalog_uses_wal(tmp_path):
    # Phase 2 needs WAL so the capture thread can write while the TUI reads.
    cat = Catalog(str(tmp_path / "w.db"))
    mode = cat.conn.execute("PRAGMA journal_mode").fetchone()[0]
    cat.close()
    assert mode.lower() == "wal"


def test_run_live_has_no_tui_flag():
    from glyph.cli import build_parser
    args = build_parser().parse_args(["run", "live", "https://x.test", "--no-tui"])
    assert args.no_tui is True


def test_live_dashboard_streams(tmp_path, monkeypatch):
    """The live dashboard shows flows written by the capture worker as they
    arrive. Capture is faked (no browser); the streaming + refresh is real."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")

    import glyph.capture.driver as drv
    from glyph.catalog import Flow

    def fake_capture(cat, url, **kw):
        cat.set_meta("capture_status", "running")
        for i in range(3):
            cat.add_flow(Flow(method="GET", url=f"https://x/{i}", host="",
                              path="", source="playwright:xhr"))
        cat.set_meta("capture_status", "done")
        return {"flows": 3, "pages": 0, "labels": 0,
                "by_source": {"playwright:xhr": 3}, "error": None}

    monkeypatch.setattr(drv, "capture_url", fake_capture)
    from glyph.tui.app import GlyphApp
    db = str(tmp_path / "l.db")
    app = GlyphApp(home=False, db_path=db, live={"url": "https://x", "kwargs": {}})

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause(1.3)  # let the first 1s refresh tick fire
            assert app.query_one("#t_flows").row_count == 3
            assert app.screen._done is True  # capture finished -> header flips

    asyncio.run(go())


def test_quit_confirmation_can_cancel_and_confirm(tmp_path, monkeypatch):
    """Quit is deliberate: q opens a modal, cancel keeps the app alive, and
    confirmation delegates to the graceful shutdown hook."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")
    from glyph.tui.app import GlyphApp, QuitConfirmScreen

    app = GlyphApp(home=False, db_path=str(tmp_path / "q.db"), live=None)
    requested = []
    monkeypatch.setattr(app, "request_shutdown", lambda: requested.append(True))

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, QuitConfirmScreen)
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "DashboardScreen"
            await pilot.press("q")
            await pilot.pause()
            await pilot.click("#quit-confirm")
            await pilot.pause()
            assert requested == [True]

    asyncio.run(go())


def test_native_quit_shortcuts_require_confirmation(tmp_path):
    """Textual's native Ctrl+Q/Ctrl+C routes must not bypass the dialog."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")
    from glyph.tui.app import GlyphApp, QuitConfirmScreen

    async def go():
        for key in ("ctrl+q", "ctrl+c"):
            home = key == "ctrl+c"
            app = GlyphApp(home=home, db_path=str(tmp_path / f"{key}.db"), live=None)
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press(key)
                await pilot.pause()
                assert isinstance(app.screen, QuitConfirmScreen)
                assert app._shutdown_requested is False

    asyncio.run(go())


def test_confirmed_quit_waits_for_workers_and_finishes(tmp_path, monkeypatch):
    """The real confirmation path signals workers and exits after they finish."""
    import asyncio
    import threading

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")
    from glyph.tui.app import GlyphApp, QuitConfirmScreen
    from textual.widgets import Static

    app = GlyphApp(home=False, db_path=str(tmp_path / "wait.db"), live=None)
    release = threading.Event()
    worker_started = threading.Event()
    worker_finished = threading.Event()
    shutdown_finished = threading.Event()

    def worker():
        worker_started.set()
        release.wait(timeout=2)
        worker_finished.set()

    def finish():
        shutdown_finished.set()

    monkeypatch.setattr(app, "_finish_shutdown", finish)

    async def go():
        async with app.run_test() as pilot:
            app.start_background(worker, name="test-worker")
            for _ in range(20):
                await pilot.pause(0.05)
                if worker_started.is_set():
                    break
            assert worker_started.is_set()
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, QuitConfirmScreen)
            await pilot.click("#quit-confirm")
            await pilot.pause()
            assert app._shutdown_requested is True
            assert str(app.screen.query_one("#quit-copy", Static).render()) == (
                "Finishing active work… Glyph will close when it is safe.")
            assert worker_finished.is_set() is False
            release.set()
            for _ in range(30):
                await pilot.pause(0.05)
                if shutdown_finished.is_set():
                    break
            assert worker_finished.is_set() is True
            assert shutdown_finished.is_set() is True

    asyncio.run(go())


def test_target_picker_switches_to_previous_target(tmp_path):
    """The TUI target picker activates a stored target and reloads its view."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")
    from glyph.catalog import Catalog, Flow
    from glyph.tui.app import GlyphApp, TargetPickerScreen

    db = str(tmp_path / "targets.db")
    cat = Catalog(db)
    first = cat.set_target("first.example")
    cat.add_flow(Flow(method="GET", url="https://first.example/", host="", path=""))
    second = cat.set_target("second.example")
    cat.add_flow(Flow(method="GET", url="https://second.example/", host="", path=""))
    cat.close()

    app = GlyphApp(home=False, db_path=db, live=None)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("t")
            await pilot.pause()
            assert isinstance(app.screen, TargetPickerScreen)
            await pilot.click(f"#target-{first}")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "DashboardScreen"
            with Catalog(db, restore_active=True) as selected:
                assert selected.target_id() == first
                assert selected.target() == "first.example"
                assert {flow.host for flow in selected.all_flows()} == {"first.example"}
            assert "first.example" in app.sub_title or "first.example" in str(
                app.query_one("#brand").render())

    asyncio.run(go())


def test_home_screen_mounts(tmp_path):
    """Bare `glyph` home screen mounts, shows the logo, and captures a URL."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")
    from glyph.tui.app import DashboardScreen, GlyphApp
    app = GlyphApp(home=True, db_path=str(tmp_path / "h.db"))

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#url").value = "example.com"
            await pilot.press("enter")          # submit URL -> dashboard
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

    asyncio.run(go())

def test_live_dashboard_honors_stage_flags(tmp_path, monkeypatch):
    """The live dashboard honors --no-sensitive / --snihunt-no-net threaded
    through the live dict (previously the TUI always ran sensitive + a
    network SNI hunt regardless of the CLI flags)."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")

    import glyph.capture.driver as drv
    import glyph.sensitive as sens
    import glyph.snihunt as sh
    from glyph.catalog import Flow

    calls = {"scan": 0, "hunt": []}

    def fake_capture(cat, url, **kw):
        cat.set_meta("capture_status", "running")
        cat.add_flow(Flow(method="GET", url="https://x.test/api", host="",
                          path="", source="playwright:xhr"))
        cat.set_meta("capture_status", "done")
        return {"flows": 1, "pages": 0, "labels": 0,
                "by_source": {"playwright:xhr": 1}, "error": None}

    def fake_scan(cat):
        calls["scan"] += 1

    def fake_hunt(cat, net=True, progress=None):
        calls["hunt"].append(net)

    monkeypatch.setattr(drv, "capture_url", fake_capture)
    monkeypatch.setattr(sens, "run_scan", fake_scan)
    monkeypatch.setattr(sh, "run_hunt", fake_hunt)

    from glyph.tui.app import GlyphApp
    db = str(tmp_path / "f.db")
    app = GlyphApp(home=False, db_path=db, live={
        "url": "https://x.test", "kwargs": {},
        "no_sensitive": True, "no_snihunt": False, "snihunt_no_net": True})

    async def go():
        async with app.run_test() as pilot:
            # Poll until the finalize worker has run (capture is faked so it
            # finishes fast; the 1s tick flips the header, then _finalize runs
            # the analysis). Fixed sleeps are flaky on slow machines.
            for _ in range(40):
                await pilot.pause(0.1)
                if calls["hunt"]:
                    break

    asyncio.run(go())
    assert calls["scan"] == 0          # --no-sensitive honored
    assert calls["hunt"] == [False]    # --snihunt-no-net honored (net=False)


def test_live_dashboard_honors_no_snihunt(tmp_path, monkeypatch):
    """--no-snihunt: the finalize skips the hunt entirely."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")

    import glyph.capture.driver as drv
    import glyph.sensitive as sens
    import glyph.snihunt as sh
    from glyph.catalog import Flow

    calls = {"scan": 0, "hunt": 0}

    def fake_capture(cat, url, **kw):
        cat.set_meta("capture_status", "running")
        cat.add_flow(Flow(method="GET", url="https://x.test/api", host="",
                          path="", source="playwright:xhr"))
        cat.set_meta("capture_status", "done")
        return {"flows": 1, "pages": 0, "labels": 0,
                "by_source": {"playwright:xhr": 1}, "error": None}

    def fake_scan(cat):
        calls["scan"] += 1

    def fake_hunt(cat, net=True, progress=None):
        calls["hunt"] += 1

    monkeypatch.setattr(drv, "capture_url", fake_capture)
    monkeypatch.setattr(sens, "run_scan", fake_scan)
    monkeypatch.setattr(sh, "run_hunt", fake_hunt)

    from glyph.tui.app import GlyphApp
    db = str(tmp_path / "n.db")
    app = GlyphApp(home=False, db_path=db, live={
        "url": "https://x.test", "kwargs": {},
        "no_sensitive": False, "no_snihunt": True, "snihunt_no_net": False})

    async def go():
        async with app.run_test() as pilot:
            # Poll until finalize's analysis has run (sensitive was NOT
            # skipped, so run_scan firing proves _analyze_once completed).
            for _ in range(40):
                await pilot.pause(0.1)
                if calls["scan"] >= 1:
                    break

    asyncio.run(go())
    assert calls["scan"] >= 1      # sensitive still runs (flag off)
    assert calls["hunt"] == 0      # --no-snihunt honored


def test_live_dashboard_shows_capture_error(tmp_path, monkeypatch):
    """A failed capture shows ✗ failed + the error in the header (previously
    it looked like ✓ captured even when the capture worker errored)."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")

    import glyph.capture.driver as drv

    def fake_capture(cat, url, **kw):
        raise RuntimeError("browser crashed")

    monkeypatch.setattr(drv, "capture_url", fake_capture)

    from glyph.tui.app import GlyphApp
    db = str(tmp_path / "e.db")
    app = GlyphApp(home=False, db_path=db,
                   live={"url": "https://x.test", "kwargs": {}})

    async def go():
        async with app.run_test() as pilot:
            # Poll until the 1s tick has flipped the header to the failed state.
            for _ in range(40):
                await pilot.pause(0.1)
                if "failed" in app.sub_title:
                    break
            assert "failed" in app.sub_title
            assert "browser crashed" in app.sub_title

    asyncio.run(go())
    with Catalog(db) as cat:
        assert cat.get_meta("capture_status") == "done"
        assert cat.get_meta("capture_error") == "browser crashed"


def test_home_screen_stage_checkbox_defaults(tmp_path):
    """Session 27: the home screen lets the user pick which analysis stages
    run — every stage is ON by default EXCEPT VPN Dec, whose file input is
    hidden until the stage is ticked."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")
    from textual.widgets import Checkbox, Input
    from glyph.tui.app import GlyphApp
    app = GlyphApp(home=True, db_path=str(tmp_path / "h.db"))

    async def go():
        # 100-wide so #shell (width 82, max-width 94%) is NOT capped by the
        # terminal width — the region check below must see the full 82.
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            for sid in ("schema", "rosetta", "sensitive", "snihunt"):
                assert app.query_one(f"#st_{sid}", Checkbox).value is True
            assert app.query_one("#st_browser", Checkbox).value is False
            assert app.query_one("#st_vpndec", Checkbox).value is False
            assert app.query_one("#vpnfile", Input).disabled is True
            # CSS regression guard (Session 27): the home layout used to be
            # squeezed top-left because screen CSS on the DEFAULT screen never
            # loads in this Textual build — and no test caught it. The rules
            # now live in App.CSS; assert they actually apply.
            assert app.query_one("#shell").region.width == 82

    asyncio.run(go())


def test_home_screen_threads_browser_mode_and_stage_selection(tmp_path, monkeypatch):
    """The home screen threads both browser mode and analysis stage choices
    into the live dashboard (capture is faked)."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")

    import glyph.capture.driver as drv
    from textual.widgets import Checkbox

    def fake_capture(cat, url, **kw):
        cat.set_meta("capture_status", "done")
        return {"flows": 0, "pages": 0, "labels": 0, "by_source": {}, "error": None}

    monkeypatch.setattr(drv, "capture_url", fake_capture)
    from glyph.tui.app import DashboardScreen, GlyphApp
    app = GlyphApp(home=True, db_path=str(tmp_path / "h.db"))

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#st_sensitive", Checkbox).value = False
            app.query_one("#st_snihunt", Checkbox).value = False
            app.query_one("#st_browser", Checkbox).value = True
            app.query_one("#url").value = "example.com"
            await pilot.press("enter")          # submit URL -> dashboard
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)
            assert app.screen._no_sensitive is True
            assert app.screen._no_snihunt is True
            assert app.screen.live["kwargs"]["browse"] is True
            assert app.screen.live["kwargs"]["cdp_url"] == "http://localhost:9222"
            assert app.screen._no_schema is False  # untouched stage stays on
            assert app.screen._no_rosetta is False

    asyncio.run(go())


def test_home_browser_mode_all_tabs_and_dashboard_stop(tmp_path, monkeypatch):
    """Browser mode permits an empty URL for all-tabs capture, and the
    dashboard's Stop capture action signals the worker without touching
    Playwright objects from the UI thread."""
    import asyncio
    import time

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")
    from textual.widgets import Checkbox
    import glyph.capture.driver as drv
    from glyph.tui.app import DashboardScreen, GlyphApp

    observed = {"stop_event": None, "started": False}

    def fake_capture(cat, url, **kw):
        observed["stop_event"] = kw["stop_event"]
        observed["started"] = True
        cat.set_meta("capture_status", "running")
        while not kw["stop_event"].is_set():
            time.sleep(0.01)
        cat.set_meta("capture_status", "done")
        return {"flows": 0, "pages": 0, "labels": 0,
                "by_source": {}, "error": None, "mode": "browse-attach"}

    monkeypatch.setattr(drv, "capture_url", fake_capture)
    db = str(tmp_path / "browser-stop.db")
    app = GlyphApp(home=True, db_path=db)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#st_browser", Checkbox).value = True
            app.query_one("#url").value = ""
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert isinstance(app.screen, DashboardScreen)
            assert app.screen.live["url"] is None
            assert app.screen.live["kwargs"]["browse"] is True
            assert observed["started"] is True
            await pilot.press("s")
            for _ in range(20):
                await pilot.pause(0.05)
                if observed["stop_event"].is_set():
                    break
            assert observed["stop_event"].is_set()

    asyncio.run(go())


def test_dashboard_has_compact_brand_row(tmp_path):
    """The dashboard inherits the logo as a compact one-line brand row so the
    big banner doesn't crowd the tables (Session 27)."""
    import asyncio

    from glyph.tui.app import HAS_TEXTUAL
    if not HAS_TEXTUAL:
        import pytest
        pytest.skip("textual not installed")
    from glyph.tui.app import GlyphApp
    app = GlyphApp(home=False, db_path=str(tmp_path / "d.db"), live=None)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            brand = app.query_one("#brand")
            assert "GLYPH" in str(brand.render())

    asyncio.run(go())


def test_clip_helper():
    assert D.clip("short") == "short"
    assert D.clip(None) == ""
    out = D.clip("x" * 100, 64)
    assert len(out) == 64 and out.endswith("…")


def test_rows_clip_long_host(tmp_path, make_entry):
    """A single long host/URL must not balloon the flows column (Session 27)."""
    from glyph.capture import ingest_har
    from glyph.catalog import Catalog
    db = str(tmp_path / "c.db")
    cat = Catalog(db)
    har = tmp_path / "s.har"
    # flow_rows prefers the stored PATH over the host part of the URL, so
    # make the path itself long to prove the clip applies.
    long = "https://x.example.com/" + "a" * 90
    har.write_text(json.dumps({"log": {"entries": [make_entry("GET", long)]}}))
    ingest_har(cat, str(har))
    _, rows = D.flow_rows(cat)
    assert len(rows[0][5]) <= 72
    assert rows[0][5].endswith("…")
    cat.close()
