"""The Glyph dashboard — a Textual TUI over a catalog (`glyph.db`).

Phase 1: read-only exploration. Five tabbed views (Flows / DOM / Schema /
Sensitive / Rosetta) with a summary header and a flow request/response
drill-in. The app only *reads* the catalog — all analysis already happened
in the headless pipeline (ADR-9). Live streaming is Phase 2.
"""
from __future__ import annotations

from typing import Optional

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import (
        DataTable,
        Footer,
        Header,
        Static,
        TabbedContent,
        TabPane,
    )
    HAS_TEXTUAL = True
except ImportError:  # pragma: no cover
    HAS_TEXTUAL = False

from glyph.catalog import Catalog
from glyph.tui import data as D

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
        f"  [b cyan]FLOWS[/]  [b]{s.get('flows', 0)}[/]  [grey58]{types}[/]"
        f"     [b cyan]SCHEMA[/]  [b]{s.get('fields', 0)}[/] fields · {s.get('enums', 0)} enums"
        f"     [b cyan]FINDINGS[/]  [b]{s.get('findings', 0)}[/]  {sevs}{noise}"
        f"     [b cyan]DOM[/]  [b]{s.get('dom_labels', 0)}[/]  [grey58]{doms}[/]"
        f"     [b cyan]ROSETTA[/]  [b]{s.get('decoded', 0)}[/] decoded"
    )


if HAS_TEXTUAL:

    class FlowDetail(ModalScreen):
        """Request/response detail for one flow."""

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

    class GlyphDashboard(App):
        CSS = """
        #summary { height: 1; padding: 0 0; color: $text; }
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
            Binding("q", "quit", "Quit"),
        ]

        def __init__(self, db_path: str) -> None:
            super().__init__()
            self.db_path = db_path

        def compose(self) -> "ComposeResult":
            yield Header(show_clock=True)
            yield Static("", id="summary", markup=True)
            with TabbedContent(initial="flows"):
                for tab_id, title, _ in _VIEWS:
                    with TabPane(title, id=tab_id):
                        yield DataTable(id=f"t_{tab_id}", zebra_stripes=True)
            yield Footer()

        def on_mount(self) -> None:
            self.title = "GLYPH"
            self.sub_title = "Live Capture"
            self.action_reload()

        def action_reload(self) -> None:
            cat = Catalog(self.db_path)
            try:
                s = D.summary(cat)
                self.sub_title = s.get("target") or "catalog"
                self.query_one("#summary", Static).update(_summary_markup(s))
                for tab_id, _, fn in _VIEWS:
                    self._fill(f"#t_{tab_id}", fn(cat))
            finally:
                cat.close()

        def _fill(self, selector: str, rows) -> None:
            headers, data = rows
            t = self.query_one(selector, DataTable)
            t.clear(columns=True)
            t.add_columns(*headers)
            for row in data:
                t.add_row(*row)
            t.cursor_type = "row"

        def action_show(self, tab: str) -> None:
            self.query_one(TabbedContent).active = tab

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
                self.push_screen(FlowDetail(detail))


def run_dashboard(db_path: str) -> None:
    """Open the dashboard on a catalog. Requires the `tui` extra."""
    if not HAS_TEXTUAL:
        raise RuntimeError(
            "Textual is not installed. Install the tui extra:\n"
            "  pip install 'glyph-re[tui]'")
    GlyphDashboard(db_path).run()
