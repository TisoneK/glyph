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
        Vertical,
        VerticalScroll,
    )
    from textual.screen import ModalScreen, Screen
    from textual.widgets import (
        Button,
        Checkbox,
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
from glyph.tui.logo import TAGLINE, logo_compact, logo_renderable

_VIEWS = [
    ("flows", "Flows", D.flow_rows),
    ("dom", "DOM", D.dom_rows),
    ("schema", "Schema", D.schema_rows),
    ("sensitive", "Sensitive", D.sensitive_rows),
    ("rosetta", "Rosetta", D.rosetta_rows),
    ("snihunt", "SNI Hunt", D.snihunt_rows),
    ("vpndec", "VPN Dec", D.vpndec_rows),
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
    sni = s.get("sni_candidates", 0)
    sni_sev = s.get("sni_by_severity", {}) or {}
    sni_color = "grey58"
    for k, c in (("high", "red"), ("medium", "yellow"), ("low", "grey58")):
        if sni_sev.get(k):
            sni_color = c
            break
    sni_str = f"[{sni_color}]{sni} sni[/]" if sni else "[grey58]0 sni[/]"
    vpns = s.get("vpn_configs", 0)
    vpn_ok = s.get("vpn_decoded", 0)
    vpn_str = (f"[green]{vpn_ok}[/]/[b]{vpns}[/] vpn" if vpns
               else "[grey58]0 vpn[/]")
    return (
        f"  [b cyan]FLOWS[/] [b]{s.get('flows', 0)}[/] [grey58]{types}[/]"
        f"    [b cyan]SCHEMA[/] [b]{s.get('fields', 0)}[/] fields · {s.get('enums', 0)} enums"
        f"    [b cyan]FINDINGS[/] [b]{s.get('findings', 0)}[/] {sevs}{noise}"
        f"    [b cyan]DOM[/] [b]{s.get('dom_labels', 0)}[/] [grey58]{doms}[/]"
        f"    [b cyan]ROSETTA[/] [b]{s.get('decoded', 0)}[/]"
        f"    [b cyan]SNI[/] {sni_str}"
        f"    [b cyan]VPN[/] {vpn_str}"
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
        BINDINGS = [Binding("q,escape", "app.quit", "Quit")]

        #: analysis stages the user can tick. Every stage ships ON by default
        #: except vpndec — it needs a config FILE to point at, not captured
        #: traffic, so it gets its own file input below the list.
        STAGES = [
            ("schema", "Schema inference"),
            ("rosetta", "Rosetta decode"),
            ("sensitive", "Sensitive / risk scan"),
            ("snihunt", "SNI bug-host hunt"),
        ]

        def compose(self) -> "ComposeResult":
            yield Header(show_clock=True)
            with Center():
                with Vertical(id="shell"):
                    yield Static(logo_renderable(), id="logo")
                    yield Static(TAGLINE, id="tag")
                    yield Input(
                        placeholder="https://target.example.com  —  enter a URL to capture",
                        id="url")
                    with Vertical(id="stages"):
                        yield Static("ANALYSIS STAGES", classes="stages-title")
                        with Horizontal(classes="stages-row"):
                            for sid, label in self.STAGES[:2]:
                                yield Checkbox(label, id=f"st_{sid}", value=True)
                        with Horizontal(classes="stages-row"):
                            for sid, label in self.STAGES[2:]:
                                yield Checkbox(label, id=f"st_{sid}", value=True)
                            yield Checkbox("VPN config decode", id="st_vpndec")
                        yield Input(
                            placeholder="path to a VPN config (.hc/.ehi/.dark/.ziv/.tls)",
                            id="vpnfile", disabled=True)
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

        def _checked_stages(self) -> list:
            """The analysis stages currently ticked (excludes vpndec — it's
            file-based and handled separately via ``vpndec_file``)."""
            return [sid for sid, _ in self.STAGES
                    if self.query_one(f"#st_{sid}", Checkbox).value]

        def _capture(self, url: str) -> None:
            url = (url or "").strip()
            if not url:
                self.app.bell()
                return
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            vpn_file = ""
            if self.query_one("#st_vpndec", Checkbox).value:
                vpn_file = self.query_one("#vpnfile", Input).value.strip()
                if not vpn_file:
                    # Tick the stage but no file: never a silent no-op.
                    self.app.bell()
            live = {
                "url": url,
                "kwargs": {"explore": 2, "settle_ms": 3000, "timeout_ms": 30000,
                           "wait_selector": None,
                           "proxy": os.environ.get("GLYPH_PROXY")},
                "stages": self._checked_stages(),
                "vpndec_file": vpn_file or None,
            }
            self.app.push_screen(DashboardScreen(self.app.db_path, live=live))

        def on_checkbox_changed(self, event) -> None:
            # The VPN Dec stage needs a config FILE — reveal its input only
            # when the stage is checked.
            if event.checkbox.id == "st_vpndec":
                self.query_one("#vpnfile", Input).disabled = not event.value

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
        BINDINGS = [
            Binding("1", "show('flows')", "Flows"),
            Binding("2", "show('dom')", "DOM"),
            Binding("3", "show('schema')", "Schema"),
            Binding("4", "show('sensitive')", "Sensitive"),
            Binding("5", "show('rosetta')", "Rosetta"),
            Binding("6", "show('snihunt')", "SNI Hunt"),
            Binding("7", "show('vpndec')", "VPN Dec"),
            Binding("r", "reload", "Reload"),
            Binding("escape", "back", "Back"),
            Binding("q", "app.quit", "Quit"),
        ]

        def __init__(self, db_path: str, live: Optional[dict] = None) -> None:
            super().__init__()
            self.db_path = db_path
            self.live = live
            live = live or {}
            # Stage selection: the home screen checkboxes (Session 27) take
            # precedence; `glyph run live` still threads the opt-out flags
            # through cli/run._open_live_dashboard, so both surfaces work.
            stages = live.get("stages")
            if stages is not None:
                sel = set(stages)
                self._no_schema = "schema" not in sel
                self._no_rosetta = "rosetta" not in sel
                self._no_sensitive = "sensitive" not in sel
                self._no_snihunt = "snihunt" not in sel
            else:
                self._no_schema = False
                self._no_rosetta = False
                self._no_sensitive = bool(live.get("no_sensitive"))
                self._no_snihunt = bool(live.get("no_snihunt"))
            self._snihunt_no_net = bool(live.get("snihunt_no_net"))
            self._vpndec_file = live.get("vpndec_file") or None
            self._start = None
            self._done = live.get("url") is None
            self._analyzing = False   # guard: never overlap analysis passes
            self._live_timers = []

        _MAX_ROWS = 800  # cap table rows so live refresh stays snappy

        def compose(self) -> "ComposeResult":
            yield Header(show_clock=True)
            yield Static("", id="brand", markup=True)
            yield Static("", id="summary", markup=True)
            with TabbedContent(initial="flows"):
                for tab_id, title, _ in _VIEWS:
                    with TabPane(title, id=tab_id):
                        yield DataTable(id=f"t_{tab_id}", zebra_stripes=True)
            yield Footer()

        def on_mount(self) -> None:
            import time
            self.app.title = "GLYPH"
            self._set_brand()
            self.action_reload()
            if self.live:
                self._start = time.monotonic()
                self.app.run_worker(self._capture_worker, thread=True, name="capture")
                # Light 1s tick (summary + visible tab) + guarded analysis.
                self._live_timers.append(self.set_interval(1.0, self._tick))
                self._live_timers.append(self.set_interval(4.0, self._analyze_tick))
            else:
                cat = Catalog(self.db_path, restore_active=True)
                try:
                    self.app.sub_title = D.clip(cat.target() or "catalog", 48)
                finally:
                    cat.close()

        def _set_brand(self) -> None:
            """One-line brand row: the compact logo + the current host. The
            host is clipped so a single long host can't stretch the header
            (Session 27)."""
            from urllib.parse import urlparse
            from rich.text import Text
            host = ""
            url = (self.live or {}).get("url")
            if url:
                host = urlparse(url).hostname or ""
            if not host:
                cat = Catalog(self.db_path, restore_active=True)
                try:
                    host = cat.target() or ""
                finally:
                    cat.close()
            t = Text()
            t.append_text(logo_compact())
            if host:
                t.append("  " + D.clip(host, 44), style="dim")
            self.query_one("#brand", Static).update(t)

        # -- live capture + refresh --------------------------------------
        def _capture_worker(self) -> None:
            from glyph.capture.driver import capture_url
            from urllib.parse import urlparse
            cat = Catalog(self.db_path)
            try:
                # ADR-12: activate this target + clear only its old rows.
                # Other targets in the catalog coexist; a re-run of the
                # same target replaces its data.
                host = urlparse(self.live["url"]).hostname
                if host:
                    cat.set_target(host)
                    cat.clear_target()
                capture_url(cat, self.live["url"], **self.live["kwargs"])
            except Exception as exc:
                try:
                    cat.set_meta("capture_status", "done")
                    cat.set_meta("capture_error", str(exc).splitlines()[0])
                except Exception:
                    pass
            finally:
                cat.close()

        def _capture_state(self) -> dict:
            """Capture + vpndec status/error in ONE Catalog open — the 1s tick
            polls every second, so avoid several connections per tick."""
            cat = Catalog(self.db_path, restore_active=True)
            try:
                return {
                    "status": cat.get_meta("capture_status"),
                    "error": cat.get_meta("capture_error"),
                    "vpndec_status": cat.get_meta("vpndec_status"),
                    "vpndec_error": cat.get_meta("vpndec_error"),
                }
            finally:
                cat.close()

        def _tick(self) -> None:
            import time
            self._refresh_live()  # summary + visible tab only (cheap)
            elapsed = int(time.monotonic() - (self._start or time.monotonic()))
            mm, ss = divmod(elapsed, 60)
            st = self._capture_state()
            if st["status"] == "done":
                if st["error"]:
                    # A failed capture must never look like success.
                    self.app.sub_title = (f"✗ failed · {mm:02d}:{ss:02d} · "
                                          f"{st['error'][:44]}")
                else:
                    sub = f"✓ captured · {mm:02d}:{ss:02d}"
                    if self._vpndec_file:
                        if st["vpndec_error"]:
                            sub += f" · vpndec ✗ {st['vpndec_error'][:32]}"
                        elif st["vpndec_status"]:
                            sub += f" · vpndec ✓ {st['vpndec_status']}"
                    self.app.sub_title = sub
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

        def _target_host(self) -> Optional[str]:
            """The capture target's host (from the live url), so analysis
            lanes re-activate it — a fresh Catalog has no active target, and
            writes would otherwise fall into the (unassigned) bucket."""
            from urllib.parse import urlparse
            url = (self.live or {}).get("url")
            return urlparse(url).hostname if url else None

        def _analyze_once(self) -> None:
            # ADR-15: schema→rosetta + sensitive run CONCURRENTLY as lanes of
            # glyph.pipeline.run_analysis (each lane target-anchored). The SNI
            # hunt is finalize-only (ADR-10 — bounded network recon too slow
            # to repeat every tick), so it's skipped on live ticks.
            from glyph.pipeline import run_analysis
            try:
                run_analysis(
                    self.db_path,
                    target=self._target_host(),
                    no_schema=self._no_schema,
                    no_rosetta=self._no_rosetta,
                    no_sensitive=self._no_sensitive,
                    no_snihunt=True,  # hunt runs once at finalize
                )
            except Exception:
                pass  # transient lock while capture writes: retry next tick
            finally:
                self._analyzing = False

        def _finalize(self) -> None:
            # Full parallel analysis INCLUDING the SNI hunt (ADR-15): all
            # lanes (schema→rosetta, sensitive, snihunt) run concurrently, so
            # the hunt no longer waits for the other stages. --no-snihunt
            # skips it; --snihunt-no-net keeps it local-only (ADR-10).
            from glyph.pipeline import run_analysis
            try:
                run_analysis(
                    self.db_path,
                    target=self._target_host(),
                    no_schema=self._no_schema,
                    no_rosetta=self._no_rosetta,
                    no_sensitive=self._no_sensitive,
                    no_snihunt=self._no_snihunt,
                    snihunt_no_net=self._snihunt_no_net,
                )
            except Exception:
                pass  # network/lock hiccup — the snihunt CLI can re-run it
            if self._vpndec_file:
                self._decode_vpndec()
            # stop the live timers now that capture is done (no more polling).
            for t in self._live_timers:
                try:
                    t.stop()
                except Exception:
                    pass
            self._live_timers = []
            self.app.call_from_thread(self.action_reload)  # one full refresh

        def _decode_vpndec(self) -> None:
            """Decode the VPN config file picked on the home screen into the
            catalog — the same path as `glyph vpndec <file>` (ADR-11), run
            once at finalize like the SNI hunt. Status/error land in meta so
            the 1s tick can surface them in the header."""
            import os
            from glyph.vpndec import decode_file
            from glyph.vpndec.keys import KeyStore
            cat = Catalog(self.db_path, restore_active=True)
            try:
                cat.set_meta("vpndec_status", "")
                cat.set_meta("vpndec_error", "")
            finally:
                cat.close()
            try:
                keys = KeyStore(os.environ.get("GLYPH_VPNKEYFILE"))
                cfg = decode_file(self._vpndec_file, keys=keys)
                cat = Catalog(self.db_path, restore_active=True)
                try:
                    cat.add_vpn_config(cfg)
                    cat.set_meta("vpndec_status", cfg.decryption_status)
                finally:
                    cat.close()
            except Exception as exc:
                cat = Catalog(self.db_path, restore_active=True)
                try:
                    cat.set_meta("vpndec_error",
                                 str(exc).splitlines()[0] or str(exc))
                finally:
                    cat.close()

        # -- rendering ---------------------------------------------------
        def _refresh_live(self) -> None:
            """Cheap refresh: summary + only the visible tab's table."""
            cat = Catalog(self.db_path, restore_active=True)
            try:
                self.query_one("#summary", Static).update(_summary_markup(D.summary(cat)))
                active = self.query_one(TabbedContent).active
                fn = dict((v[0], v[2]) for v in _VIEWS).get(active)
                if fn:
                    self._fill(f"#t_{active}", fn(cat))
            finally:
                cat.close()

        def action_reload(self) -> None:
            cat = Catalog(self.db_path, restore_active=True)
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
                cat = Catalog(self.db_path, restore_active=True)
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
            cat = Catalog(self.db_path, restore_active=True)
            try:
                detail = D.flow_detail(cat, flow_id)
            finally:
                cat.close()
            if detail:
                self.app.push_screen(FlowDetail(detail))

    class GlyphApp(App):
        """Top-level app: opens on the home screen, or straight to a dashboard."""

        # Screen CSS lives HERE (App.CSS), not on the Screen classes: this
        # Textual build only loads a screen's CSS when the screen is pushed or
        # switched — the DEFAULT screen's CSS never loads, so screen-scoped
        # rules silently did nothing (the home page's pre-existing "squeezed
        # top-left" layout). Selectors are type-scoped so rules never leak
        # between screens.
        CSS = """
        HomeScreen { align: center middle; }
        HomeScreen #shell { width: 82; max-width: 94%; height: auto; padding: 0 1; }
        HomeScreen #logo { content-align: center middle; height: auto; }
        HomeScreen #tag { content-align: center middle; color: $text-muted; margin: 0 0 1 0; }
        HomeScreen #url { margin: 0 0 1 0; }
        HomeScreen #stages { border: round $primary; padding: 1 2; height: auto; margin: 0 0 1 0; }
        HomeScreen .stages-title { text-style: bold; color: $primary; margin: 0 0 1 0; }
        HomeScreen .stages-row { height: auto; }
        HomeScreen .stages-row Checkbox { margin: 0 4 0 0; }
        HomeScreen #vpnfile { margin: 1 0 0 0; }
        HomeScreen #actions { height: auto; align: center middle; margin: 0 0 1 0; }
        HomeScreen #actions Button { margin: 0 1; }
        HomeScreen #hint { content-align: center middle; color: $text-muted; }
        DashboardScreen #brand { height: 1; }
        DashboardScreen #summary { height: 1; }
        DashboardScreen TabbedContent { height: 1fr; }
        DashboardScreen DataTable { height: 1fr; }
        FlowDetail #detail { padding: 1 2; }
        """

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
