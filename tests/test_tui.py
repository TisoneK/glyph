"""TUI data adapters + dashboard/flows/dom CLI wiring.

The Textual app itself is smoke-tested via its async test harness; the data
adapters (the real logic) are pure and covered directly.
"""
from __future__ import annotations

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
    from glyph.tui.app import GlyphDashboard
    db = str(tmp_path / "l.db")
    app = GlyphDashboard(db, live={"url": "https://x", "kwargs": {}})

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause(1.3)  # let the first 1s refresh tick fire
            assert app.query_one("#t_flows").row_count == 3
            assert app._done is True  # capture finished -> header flips

    asyncio.run(go())
