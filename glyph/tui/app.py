"""The Glyph TUI — a home/splash screen and the live dashboard.

`glyph` (no args) opens the home screen: the GLYPH wordmark and a target
box. Enter a URL → the live dashboard captures and streams it in real time
(ADR-9 Phase 2). `glyph dashboard` / `glyph run live` jump straight to the
dashboard. The app only reads/refreshes the catalog; the analysis engine
stays headless.
"""
from __future__ import annotations

import os
from typing import Optional

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import (
        Center,
        Horizontal,
        Middle,
        Vertical,
        VerticalScroll,
    )
    from textual.screen import ModalScreen, Screen
    from textual.widgets import (
        Button,
        DataTable,
        Footer,
        Header,
        Input,
        Static,
        TabbedContent,
        TabPane,
    )
    HAS_TEXTUAL = True
except ImportError:  # pragma: no cover
    HAS_TEXTUAL = False

from glyph.catalog import Catalog
from glyph.tui import data as D
from glyph.tui.logo import TAGLINE, logo_renderable

_VIEWS = [
    ("flows", "Flows", D.flow_rows),
    ("dom", "DOM", D.dom_rows),
    ("schema", "Schema", D.schema_rows),
    ("sensitive", "Sensitive", D.sensitive_rows),
    ("rosetta", "Rosetta", D.rosetta_rows),
]


def _summary_markup(s: dict) -> str:
    t = s.get("by_type", {})
    types = " · ".join(f"{t[k]} {k}" for k in ("xhr", "fetch", "document", "script")
                       if t.get(k)) or "—"
    sev = s.get("by_severity", {})
    sevs = " · ".join(f"[{c}]{sev[k]} {k}[/]" for k, c in
                      (("critical", "bold red"), ("high", "red"),
                       ("medium", "yellow"), ("low", "grey58")) if sev.get(k)) or "—"
    noise = f" · [grey58]+{s['tracking_noise']} noise[/]" if s.get("tracking_noise") else ""
    dtags = s.get("dom_by_tag", {})
    doms = " · ".join(f"{dtags[k]} {k}" for k in ("button", "input", "a", "span")
                      if dtags.get(k)) or f"{s.get('dom_labels', 0)} labels"
    return (
        f"  [b cyan]FLOWS[/] [b]{s.get('flows', 0)}[/] [grey58]{types}[/]"
        f"    [b cyan]SCHEMA[/] [b]{s.get('fields', 0)}[/] fields · {s.get('enums', 0)} enums"
        f"    [b cyan]FINDINGS[/] [b]{s.get('findings', 0)}[/] {sevs}{noise}"
        f"    [b cyan]DOM[/] [b]{s.get('dom_labels', 0)}[/] [grey58]{doms}[/]"
        f"    [b cyan]ROSETTA[/] [b]{s.get('decoded', 0)}[/]"
    )


if HAS_TEXTUAL:

    class FlowDetail(ModalScreen):
        BINDINGS = [Binding("escape,q,enter", "close", "Close")]

        def __init__(self, detail: dict) -> None:
            super().__init__()
            self.detail = detail

        def compose(self) -> "ComposeResult":
            d = self.detail

            def hdrs(h: dict) -> str:
                return "\n".join(f"    {k}: {v}" for k, v in list(h.items())[:25]) \
                    or "    (none)"

            text = (
                f"[b]{d['method']} {d['url']}[/b]\n\n"
                f"[b cyan]REQUEST[/]\n{hdrs(d['req_headers'])}\n\n"
                f"  body:\n{(d.get('req_body') or '(none)')[:2000]}\n\n"
                f"[b cyan]RESPONSE[/]  [b]{d.get('status')}[/]  "
                f"[grey58]{d.get('resp_mime') or ''}[/]\n{hdrs(d['resp_headers'])}\n\n"
                f"{(d.get('resp_body') or '(none)')[:4000]}"
            )
            yield VerticalScroll(Static(text, markup=True), id="detail")

        def action_close(self) -> None:
            self.app.pop_screen()

    class HomeScreen(Screen):
        CSS = """
        HomeScreen { align: center middle; }
        #box { width: 66; height: auto; }
        #logo { content-align: center middle; height: auto; padding: 1 0 0 0; }
        #tag { content-align: center middle; color: $text-muted; padding: 0 0 1 0; }
        #url { margin: 1 0; }
        #actions { height: auto; align: center middle; padding: 1 0; }
        #actions Button { margin: 0 1; }
        #hint { content-align: center middle; color: $text-muted; }
        """
        BINDINGS = [Binding("q,escape", "app.quit", "Quit")]

        def compose(self) -> "ComposeResult":
            yield Header(show_clock=True)
            with Middle():
                with Center():
                    with Vertical(id="box"):
                        yield Static(logo_renderable(), id="logo")
                        yield Static(TAGLINE, id="tag")
                        yield Input(
                            placeholder="https://target.example.com  —  enter a URL to capture",
                            id="url")
                        with Horizontal(id="actions"):
                            yield Button("Capture ▶", id="capture", variant="primary")
                            yield Button("Open catalog", id="open")
                            yield Button("Quit", id="quit", variant="error")
                        yield Static("[dim]Enter a URL and press Enter · "
                                     "or open the existing catalog[/]", id="hint")
            yield Footer()

        def on_mount(self) -> None:
            self.app.title = "GLYPH"
            self.app.sub_title = "reverse-engineering toolkit"
            self.query_one("#url", Input).focus()

        def _capture(self, url: str) -> None:
            url = (url or "").strip()
            if not url:
                self.app.bell()
                return
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            live = {"url": url, "kwargs": {
                "explore": 2, "settle_ms": 3000, "timeout_ms": 30000,
                "wait_selector": None, "proxy": os.environ.get("GLYPH_PROXY")}}
            self.app.push_screen(DashboardScreen(self.app.db_path, live=live))

        def on_input_submitted(self, event) -> None:
            self._capture(event.value)

        def on_button_pressed(self, event) -> None:
            if event.button.id == "capture":
                self._capture(self.query_one("#url", Input).value)
            elif event.button.id == "open":
                self.app.push_screen(DashboardScreen(self.app.db_path, live=None))
            elif event.button.id == "quit":
                self.app.exit()

    class DashboardScreen(Screen):
        CSS = """
        #summary { height: 1; }
        TabbedContent { height: 1fr; }
        DataTable { height: 1fr; }
        #detail { padding: 1 2; }
        """
        BINDINGS = [
            Binding("1", "show('flows')", "Flows"),
            Binding("2", "show('dom')", "DOM"),
            Binding("3", "show('schema')", "Schema"),
            Binding("4", "show('sensitive')", "Sensitive"),
            Binding("5", "show('rosetta')", "Rosetta"),
            Binding("r", "reload", "Reload"),
            Binding("escape", "back", "Back"),
            Binding("q", "app.quit", "Quit"),
        ]

        def __init__(self, db_path: str, live: Optional[dict] = None) -> None:
            super().__init__()
            self.db_path = db_path
            self.live = live
            self._start = None
            self._done = live is None
            self._analyzing = False   # guard: never overlap analysis passes
            self._live_timers = []

        _MAX_ROWS = 800  # cap table rows so live refresh stays snappy

        def compose(self) -> "ComposeResult":
            yield Header(show_clock=True)
            yield Static("", id="summary", markup=True)
            with TabbedContent(initial="flows"):
                for tab_id, title, _ in _VIEWS:
                    with TabPane(title, id=tab_id):
                        yield DataTable(id=f"t_{tab_id}", zebra_stripes=True)
            yield Footer()

        def on_mount(self) -> None:
            import time
            self.app.title = "GLYPH"
            self.action_reload()
            if self.live:
                self._start = time.monotonic()
                self.app.run_worker(self._capture_worker, thread=True, name="capture")
                # Light 1s tick (summary + visible tab) + guarded analysis.
                self._live_timers.append(self.set_interval(1.0, self._tick))
                self._live_timers.append(self.set_interval(4.0, self._analyze_tick))
            else:
                cat = Catalog(self.db_path)
                try:
                    self.app.sub_title = cat.target() or "catalog"
                finally:
                    cat.close()

        # -- live capture + refresh --------------------------------------
        def _capture_worker(self) -> None:
            from glyph.capture.driver import capture_url
            cat = Catalog(self.db_path)
            try:
                cat.reset()  # fresh catalog — show only THIS target
                capture_url(cat, self.live["url"], **self.live["kwargs"])
            except Exception as exc:
                try:
                    cat.set_meta("capture_status", "done")
                    cat.set_meta("capture_error", str(exc).splitlines()[0])
                except Exception:
                    pass
            finally:
                cat.close()

        def _status(self) -> Optional[str]:
            cat = Catalog(self.db_path)
            try:
                return cat.get_meta("capture_status")
            finally:
                cat.close()

        def _tick(self) -> None:
            import time
            self._refresh_live()  # summary + visible tab only (cheap)
            elapsed = int(time.monotonic() - (self._start or time.monotonic()))
            mm, ss = divmod(elapsed, 60)
            if self._status() == "done":
                self.app.sub_title = f"✓ captured · {mm:02d}:{ss:02d}"
                if not self._done:
                    self._done = True
                    # one final analysis + full reload, then stop polling.
                    self.app.run_worker(self._finalize, thread=True, name="final")
            else:
                self.app.sub_title = f"● LIVE  {mm:02d}:{ss:02d}"

        def _analyze_tick(self) -> None:
            if self._done or self._analyzing:
                return  # never let analysis passes overlap and pile up
            self._analyzing = True
            self.app.run_worker(self._analyze_once, thread=True, name="analyze")

        def _analyze_once(self) -> None:
            from glyph.rosetta import build_dictionary
            from glyph.schema import infer_all
            from glyph.sensitive import run_scan
            cat = Catalog(self.db_path)
            try:
                infer_all(cat)
                build_dictionary(cat)
                run_scan(cat)
            except Exception:
                pass  # transient lock while capture writes: retry next tick
            finally:
                cat.close()
                self._analyzing = False

        def _finalize(self) -> None:
            self._analyze_once()
            # stop the live timers now that capture is done (no more polling).
            for t in self._live_timers:
                try:
                    t.stop()
                except Exception:
                    pass
            self._live_timers = []
            self.app.call_from_thread(self.action_reload)  # one full refresh

        # -- rendering ---------------------------------------------------
        def _refresh_live(self) -> None:
            """Cheap refresh: summary + only the visible tab's table."""
            cat = Catalog(self.db_path)
            try:
                self.query_one("#summary", Static).update(_summary_markup(D.summary(cat)))
                active = self.query_one(TabbedContent).active
                fn = dict((v[0], v[2]) for v in _VIEWS).get(active)
                if fn:
                    self._fill(f"#t_{active}", fn(cat))
            finally:
                cat.close()

        def action_reload(self) -> None:
            cat = Catalog(self.db_path)
            try:
                self.query_one("#summary", Static).update(_summary_markup(D.summary(cat)))
                for tab_id, _, fn in _VIEWS:
                    self._fill(f"#t_{tab_id}", fn(cat))
            finally:
                cat.close()

        def _fill(self, selector: str, rows) -> None:
            headers, data = rows
            if len(data) > self._MAX_ROWS:
                data = data[-self._MAX_ROWS:]  # keep the latest, stay snappy
            t = self.query_one(selector, DataTable)
            t.clear(columns=True)
            t.add_columns(*headers)
            for row in data:
                t.add_row(*row)
            t.cursor_type = "row"

        def action_show(self, tab: str) -> None:
            self.query_one(TabbedContent).active = tab

        def on_tabbed_content_tab_activated(self, event) -> None:
            # Refresh a tab's data the moment it becomes visible (since the
            # live tick only refreshes the active tab).
            active = self.query_one(TabbedContent).active
            fn = dict((v[0], v[2]) for v in _VIEWS).get(active)
            if fn:
                cat = Catalog(self.db_path)
                try:
                    self._fill(f"#t_{active}", fn(cat))
                finally:
                    cat.close()

        def action_back(self) -> None:
            # Pop back to the home screen if we came from it; otherwise quit.
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            else:
                self.app.exit()

        def on_data_table_row_selected(self, event) -> None:
            if event.data_table.id != "t_flows":
                return
            row = event.data_table.get_row(event.row_key)
            try:
                flow_id = int(row[0])
            except (ValueError, TypeError, IndexError):
                return
            cat = Catalog(self.db_path)
            try:
                detail = D.flow_detail(cat, flow_id)
            finally:
                cat.close()
            if detail:
                self.app.push_screen(FlowDetail(detail))

    class GlyphApp(App):
        """Top-level app: opens on the home screen, or straight to a dashboard."""

        def __init__(self, home: bool = True, db_path: str = "glyph.db",
                     live: Optional[dict] = None) -> None:
            super().__init__()
            self._home = home
            self.db_path = db_path
            self._live = live

        def get_default_screen(self) -> "Screen":
            if self._home:
                return HomeScreen()
            return DashboardScreen(self.db_path, live=self._live)


def run_home(db_path: str = "glyph.db") -> None:
    """Open the home/splash screen. Requires the `tui` extra."""
    _require_textual()
    GlyphApp(home=True, db_path=db_path).run()


def run_dashboard(db_path: str, live: Optional[dict] = None) -> None:
    """Open the dashboard directly (read-only, or a live capture)."""
    _require_textual()
    GlyphApp(home=False, db_path=db_path, live=live).run()


def _require_textual() -> None:
    if not HAS_TEXTUAL:
        raise RuntimeError(
            "Textual is not installed. Install the tui extra:\n"
            "  pip install 'glyph-re[tui]'")
