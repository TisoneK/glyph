"""The Glyph TUI — home, live dashboard, quit lifecycle, and target views.

`glyph` opens the home screen. Enter a URL → the dashboard captures and
streams it in real time. Core analysis is parallel; SNI hunting runs as a
separate tracked worker. The TUI remains a presentation/lifecycle layer over
the headless engine.
"""
from __future__ import annotations

import os
import threading
import time
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
    ("data", "Data", D.endpoint_data_rows),
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
    data_endpoints = s.get("data_endpoints", 0)
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
        f"    [b cyan]DATA[/] [b]{data_endpoints}[/] endpoints with bodies"
        f"    [b cyan]SCHEMA[/] [b]{s.get('fields', 0)}[/] fields · {s.get('enums', 0)} enums"
        f"    [b cyan]FINDINGS[/] [b]{s.get('findings', 0)}[/] {sevs}{noise}"
        f"    [b cyan]DOM[/] [b]{s.get('dom_labels', 0)}[/] [grey58]{doms}[/]"
        f"    [b cyan]ROSETTA[/] [b]{s.get('decoded', 0)}[/]"
        f"    [b cyan]SNI[/] {sni_str}"
        f"    [b cyan]VPN[/] {vpn_str}"
    )


if HAS_TEXTUAL:

    class QuitConfirmScreen(ModalScreen):
        """Confirm exit so a live capture never stops mid-write silently."""

        BINDINGS = [Binding("escape,n", "cancel", "No")]

        def compose(self) -> "ComposeResult":
            with Vertical(id="quit-dialog"):
                yield Static("Quit Glyph?", classes="dialog-title")
                yield Static("Finish any active capture or analysis before closing?",
                             id="quit-copy", classes="dialog-copy")
                with Horizontal(classes="dialog-actions"):
                    yield Button("Quit", id="quit-confirm", variant="error")
                    yield Button("Keep working", id="quit-cancel")

        def on_button_pressed(self, event) -> None:
            self.dismiss(event.button.id == "quit-confirm")

        def action_cancel(self) -> None:
            self.dismiss(False)


    class TargetPickerScreen(ModalScreen):
        """Choose a target already registered in the multi-target catalog."""

        BINDINGS = [Binding("escape", "cancel", "Cancel")]

        def __init__(self, targets: list, current_id: Optional[int]) -> None:
            super().__init__()
            self.targets = targets
            self.current_id = current_id

        def compose(self) -> "ComposeResult":
            with Vertical(id="target-dialog"):
                yield Static("Switch target", classes="dialog-title")
                yield Static("Choose a previously processed target to inspect.",
                             classes="dialog-copy")
                real_targets = [t for t in self.targets if t["id"] != 0]
                if not real_targets:
                    yield Static("No processed targets yet.", classes="dialog-copy")
                for target in real_targets:
                    current = "  · current" if target["id"] == self.current_id else ""
                    label = f"{target['host']}  ·  {target.get('flows', 0)} flows{current}"
                    yield Button(label, id=f"target-{target['id']}",
                                 disabled=target["id"] == self.current_id)
                with Horizontal(classes="dialog-actions"):
                    yield Button("Cancel", id="target-cancel")

        def on_button_pressed(self, event) -> None:
            button_id = event.button.id or ""
            if button_id == "target-cancel":
                self.dismiss(None)
            elif button_id.startswith("target-"):
                self.dismiss(int(button_id.split("-", 1)[1]))

        def action_cancel(self) -> None:
            self.dismiss(None)


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
        BINDINGS = [Binding("q,escape", "confirm_quit", "Quit")]

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
                        yield Static("CAPTURE MODE", classes="stages-title")
                        with Horizontal(classes="stages-row"):
                            yield Checkbox("Use my browser (live)",
                                           id="st_browser", value=False)
                        yield Static("[dim]Uses your existing Chrome/Edge/Brave via "
                                     "CDP. Leave URL empty to capture every open tab.[/dim]",
                                     id="browser-hint", markup=True)
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
            browser_mode = self.query_one("#st_browser", Checkbox).value
            if not url and not browser_mode:
                self.app.bell()
                return
            if url and not url.startswith(("http://", "https://")):
                url = "https://" + url
            vpn_file = ""
            if self.query_one("#st_vpndec", Checkbox).value:
                vpn_file = self.query_one("#vpnfile", Input).value.strip()
                if not vpn_file:
                    # Tick the stage but no file: never a silent no-op.
                    self.app.bell()
            live = {
                "url": url or None,
                "kwargs": {"explore": 2, "settle_ms": 3000, "timeout_ms": 30000,
                           "wait_selector": None,
                           "proxy": os.environ.get("GLYPH_PROXY"),
                           "browse": browser_mode,
                           "cdp_url": (os.environ.get("GLYPH_CDP_URL")
                                       or "http://localhost:9222") if browser_mode else None,
                           "browser": "chrome",
                           "user_data_dir": None,
                           "incognito": False,
                           "browser_path": None},
                "stages": self._checked_stages(),
                "vpndec_file": vpn_file or None,
            }
            self.app.push_screen(DashboardScreen(self.app.db_path, live=live))

        def on_checkbox_changed(self, event) -> None:
            # The VPN Dec stage needs a config FILE — reveal its input only
            # when the stage is checked.
            if event.checkbox.id == "st_vpndec":
                self.query_one("#vpnfile", Input).disabled = not event.value
            elif event.checkbox.id == "st_browser":
                # A URL is optional only for real-browser all-traffic mode.
                self.query_one("#url", Input).placeholder = (
                    "https://target.example.com  —  target tab + popups"
                    if event.value else
                    "https://target.example.com  —  enter a URL to capture")

        def on_input_submitted(self, event) -> None:
            self._capture(event.value)

        def action_confirm_quit(self) -> None:
            self.app.push_screen(QuitConfirmScreen(), self._quit_result)

        def _quit_result(self, confirmed: bool) -> None:
            if confirmed:
                self.app.request_shutdown()

        def on_button_pressed(self, event) -> None:
            if event.button.id == "capture":
                self._capture(self.query_one("#url", Input).value)
            elif event.button.id == "open":
                self.app.push_screen(DashboardScreen(self.app.db_path, live=None))
            elif event.button.id == "quit":
                self.action_confirm_quit()

    class DashboardScreen(Screen):
        BINDINGS = [
            Binding("1", "show('flows')", "Flows"),
            Binding("2", "show('data')", "Data"),
            Binding("3", "show('dom')", "DOM"),
            Binding("4", "show('schema')", "Schema"),
            Binding("5", "show('sensitive')", "Sensitive"),
            Binding("6", "show('rosetta')", "Rosetta"),
            Binding("7", "show('snihunt')", "SNI Hunt"),
            Binding("8", "show('vpndec')", "VPN Dec"),
            Binding("r", "reload", "Reload"),
            Binding("s", "stop_capture", "Stop capture"),
            Binding("escape", "back", "Back"),
            Binding("q", "confirm_quit", "Quit"),
            Binding("t", "targets", "Targets"),
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
            # A live browser session may intentionally have no URL (all tabs),
            # but it is still active until the browser closes or the user
            # presses Stop capture. Read-only dashboards use live=None.
            self._done = False if live else True
            self._analyzing = False   # guard: never overlap analysis passes
            self._finalizing = False
            self._analysis_lock = threading.Lock()
            self._sni_running = False
            self._capture_worker_error = None
            self._analysis_worker_error = None
            self._live_timers = []
            self._stop_event = threading.Event()

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
            try:
                self._set_brand()
                self.action_reload()
            except Exception as exc:
                # Startup reads happen before the capture worker. On Windows,
                # a bad path/permission or locked database must become a
                # visible dashboard error rather than aborting Textual.
                self._capture_worker_error = str(exc).splitlines()[0] or type(exc).__name__
                self.app.sub_title = f"✗ catalog unavailable · {self._capture_worker_error[:56]}"
            if self.live:
                self._start = time.monotonic()
                self.app.start_background(self._capture_worker, name="capture")
                # Light 1s tick (summary + visible tab) + guarded analysis.
                self._live_timers.append(self.set_interval(1.0, self._tick))
                self._live_timers.append(self.set_interval(4.0, self._analyze_tick))
            else:
                try:
                    cat = Catalog(self.db_path, restore_active=True)
                    try:
                        self.app.sub_title = D.clip(cat.target() or "catalog", 48)
                    finally:
                        cat.close()
                except Exception as exc:
                    self._capture_worker_error = str(exc).splitlines()[0] or type(exc).__name__
                    self.app.sub_title = f"✗ catalog unavailable · {self._capture_worker_error[:56]}"

        def _set_brand(self) -> None:
            """One-line brand row: the compact logo + the current host. The
            host is clipped so a single long host can't stretch the header
            (Session 27)."""
            from urllib.parse import urlparse
            from rich.text import Text
            cat = Catalog(self.db_path, restore_active=True)
            try:
                # The restored catalog target is authoritative after a
                # target switch; live URL is only a fallback during startup.
                host = cat.target() or ""
            finally:
                cat.close()
            if not host:
                url = (self.live or {}).get("url")
                host = urlparse(url).hostname if url else ""
            t = Text()
            t.append_text(logo_compact())
            if host:
                t.append("  " + D.clip(host, 44), style="dim")
            self.query_one("#brand", Static).update(t)

        # -- live capture + refresh --------------------------------------
        def _capture_worker(self) -> None:
            from glyph.capture.driver import capture_url
            from urllib.parse import urlparse
            cat = None
            try:
                # Catalog construction itself can fail on Windows (bad path,
                # permissions, or a locked/network-backed file). Keep that
                # failure on the worker's visible error channel instead of
                # letting the thread die before capture_status is written.
                cat = Catalog(self.db_path)
                self._capture_worker_error = None
                cat.set_meta("capture_error", "")
                cat.set_meta("analysis_status", "")
                cat.set_meta("analysis_error", "")
                # ADR-12: activate this target + clear only its old rows.
                # Other targets in the catalog coexist; a re-run of the
                # same target replaces its data.
                url = self.live.get("url")
                host = urlparse(url).hostname if url else None
                if host:
                    cat.set_target(host)
                    cat.clear_target()
                kwargs = dict(self.live.get("kwargs") or {})
                kwargs["stop_event"] = self._stop_event
                capture_url(cat, url, **kwargs)
            except Exception as exc:
                error = str(exc).splitlines()[0] or type(exc).__name__
                self._capture_worker_error = error
                if cat is not None:
                    try:
                        cat.set_meta("capture_status", "done")
                        cat.set_meta("capture_error", error)
                    except Exception:
                        pass
            else:
                # A successful retry must not inherit a previous failed
                # capture's error marker in the same catalog.
                try:
                    cat.set_meta("capture_error", "")
                except Exception:
                    pass
            finally:
                if cat is not None:
                    cat.close()

        def _capture_state(self) -> dict:
            """Capture + vpndec status/error in ONE Catalog open — the 1s tick
            polls every second, so avoid several connections per tick."""
            cat = Catalog(self.db_path, restore_active=True)
            try:
                return {
                    "status": cat.get_meta("capture_status"),
                    "error": cat.get_meta("capture_error") or None,
                    "analysis_status": cat.get_meta("analysis_status"),
                    "analysis_error": cat.get_meta("analysis_error") or None,
                    "vpndec_status": cat.get_meta("vpndec_status"),
                    "vpndec_error": cat.get_meta("vpndec_error"),
                }
            finally:
                cat.close()

        def _tick(self) -> None:
            import time
            try:
                self._refresh_live()  # summary + visible tab only (cheap)
                st = self._capture_state()
            except Exception as exc:
                worker_error = self._capture_worker_error
                if worker_error:
                    self._done = True
                    self.app.sub_title = f"✗ capture failed · {worker_error[:56]}"
                    self._stop_live_timers()
                    return
                # A transient SQLite/console issue must not kill Textual's
                # timer. Keep the last rendered data and expose the failure
                # instead of making Windows look completely blank.
                self.app.sub_title = f"⚠ refresh retry · {str(exc)[:56]}"
                return
            elapsed = int(time.monotonic() - (self._start or time.monotonic()))
            mm, ss = divmod(elapsed, 60)
            if self._capture_worker_error:
                self._done = True
                self.app.sub_title = (f"✗ capture failed · {mm:02d}:{ss:02d} · "
                                      f"{self._capture_worker_error[:44]}")
                self._stop_live_timers()
                return
            if self._analysis_worker_error:
                self.app.sub_title = (f"⚠ analysis retry · {mm:02d}:{ss:02d} · "
                                      f"{self._analysis_worker_error[:44]}")
            if st["status"] == "done":
                if st.get("analysis_error"):
                    self.app.sub_title = (f"✗ analysis failed · {mm:02d}:{ss:02d} · "
                                          f"{st['analysis_error'][:44]}")
                elif st["error"]:
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
                    # One final core analysis + detached SNI worker. Keep the
                    # worker tracked so quit can wait for graceful shutdown.
                    self.app.start_background(self._finalize, name="final")
            else:
                self.app.sub_title = f"● LIVE  {mm:02d}:{ss:02d}"

        def _analyze_tick(self) -> None:
            if self._done or self._analyzing:
                return  # never let analysis passes overlap and pile up
            self._analyzing = True
            self.app.start_background(self._analyze_once, name="analyze")

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
                cat = Catalog(self.db_path, restore_active=True)
                try:
                    cat.set_meta("analysis_status", "running")
                    cat.set_meta("analysis_error", "")
                finally:
                    cat.close()
                with self._analysis_lock:
                    run_analysis(
                        self.db_path,
                        target=self._target_host(),
                        no_schema=self._no_schema,
                        no_rosetta=self._no_rosetta,
                        no_sensitive=self._no_sensitive,
                    )
                cat = Catalog(self.db_path, restore_active=True)
                try:
                    cat.set_meta("analysis_status", "done")
                    cat.set_meta("analysis_error", "")
                finally:
                    cat.close()
            except Exception as exc:
                try:
                    cat = Catalog(self.db_path, restore_active=True)
                except Exception:
                    self._analysis_worker_error = (
                        str(exc).splitlines()[0] or type(exc).__name__)
                    self._analyzing = False
                    return
                try:
                    cat.set_meta("analysis_status", "failed")
                    cat.set_meta("analysis_error", str(exc).splitlines()[0] or type(exc).__name__)
                finally:
                    cat.close()
            finally:
                self._analyzing = False

        def _finalize(self) -> None:
            """Finish core analysis, then launch SNI as a separate worker.

            SNI is intentionally outside ``run_analysis``'s core pool. The
            dashboard keeps polling while that bounded network stage runs, so
            candidates appear without holding the rest of the result hostage.
            """
            from glyph.pipeline import run_analysis
            self._finalizing = True
            analysis_error = None
            analysis_ok = False
            # A final pass can collide with the last capture commit on slower
            # Windows filesystems. Retry the whole dependency chain briefly so
            # a transient SQLite lock does not permanently produce an empty
            # Rosetta tab and then stop the refresh loop.
            for attempt in range(3):
                try:
                    with self._analysis_lock:
                        run_analysis(
                            self.db_path,
                            target=self._target_host(),
                            no_schema=self._no_schema,
                            no_rosetta=self._no_rosetta,
                            no_sensitive=self._no_sensitive,
                        )
                    analysis_ok = True
                    break
                except Exception as exc:
                    analysis_error = str(exc).splitlines()[0] or type(exc).__name__
                    if attempt < 2:
                        time.sleep(0.25 * (attempt + 1))
            try:
                if analysis_ok and self._vpndec_file:
                    self._decode_vpndec()
                cat = Catalog(self.db_path, restore_active=True)
                try:
                    cat.set_meta("analysis_status", "done" if analysis_ok else "failed")
                    cat.set_meta("analysis_error", analysis_error or "")
                finally:
                    cat.close()
            except Exception as exc:
                analysis_error = str(exc).splitlines()[0] or type(exc).__name__
                try:
                    cat = Catalog(self.db_path, restore_active=True)
                    try:
                        cat.set_meta("analysis_status", "failed")
                        cat.set_meta("analysis_error", analysis_error)
                    finally:
                        cat.close()
                except Exception:
                    pass
            finally:
                self._finalizing = False
            self.app.call_from_thread(self.action_reload)
            if not analysis_ok or self._no_snihunt:
                # Do not present stale Rosetta output as complete and do not
                # start network SNI work when the core catalog pass failed.
                self.app.call_from_thread(self._stop_live_timers)
            else:
                self.app.call_from_thread(self._start_snihunt)

        def _start_snihunt(self) -> None:
            if self._sni_running or self.app._shutdown_requested:
                return
            self._sni_running = True
            self.app.start_background(self._run_snihunt, name="snihunt")

        def _run_snihunt(self) -> None:
            from glyph.pipeline import run_snihunt
            try:
                run_snihunt(
                    self.db_path,
                    target=self._target_host(),
                    snihunt_no_net=self._snihunt_no_net,
                )
            except Exception:
                pass
            finally:
                self._sni_running = False
                self.app.call_from_thread(self.action_reload)
                self.app.call_from_thread(self._stop_live_timers)

        def action_stop_capture(self) -> None:
            """Stop a live capture without closing an attached browser.

            The capture worker owns Playwright and observes this event on its
            own thread; the UI never touches Playwright objects cross-thread.
            """
            if not self.live or self._done:
                return
            self._stop_event.set()
            self.app.sub_title = "stopping capture safely…"

        def _stop_live_timers(self) -> None:
            for timer in self._live_timers:
                try:
                    timer.stop()
                except Exception:
                    pass
            self._live_timers = []

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
            """Cheap refresh: summary + only the visible tab's table.

            The data adapters are intentionally uncached: SQLite WAL reads are
            cheap, and a cache here would make newly captured Windows rows look
            missing. The only optimization is limiting work to the active tab;
            a full reload still happens on completion/tab activation.
            """
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
            """Reload all tables when the screen is still mounted.

            A worker may complete while the user is quitting or navigating
            away. Treat a missing DOM tree as a normal lifecycle race rather
            than allowing a Textual WorkerFailed exception to escape.
            """
            cat = None
            try:
                cat = Catalog(self.db_path, restore_active=True)
                self.query_one("#summary", Static).update(_summary_markup(D.summary(cat)))
                for tab_id, _, fn in _VIEWS:
                    self._fill(f"#t_{tab_id}", fn(cat))
            except Exception as exc:
                # NoMatches during teardown is expected; other failures are
                # still surfaced while keeping the worker from crashing.
                if self.is_mounted:
                    self._capture_worker_error = str(exc).splitlines()[0] or type(exc).__name__
                    try:
                        self.app.sub_title = f"⚠ reload retry · {self._capture_worker_error[:56]}"
                    except Exception:
                        pass
            finally:
                if cat is not None:
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

        def action_confirm_quit(self) -> None:
            self.app.push_screen(QuitConfirmScreen(), self._quit_result)

        def _quit_result(self, confirmed: bool) -> None:
            if confirmed:
                self.app.request_shutdown()

        def action_targets(self) -> None:
            # Do not redirect a dashboard while its capture is still writing;
            # completed live captures and read-only dashboards are safe.
            if self.app.has_active_workers():
                self.app.bell()
                return
            cat = Catalog(self.db_path, restore_active=True)
            try:
                targets = cat.targets()
                current_id = cat.target_id()
            finally:
                cat.close()
            self.app.push_screen(TargetPickerScreen(targets, current_id),
                                  self._target_selected)

        def _target_selected(self, target_id: Optional[int]) -> None:
            if target_id is None:
                return
            cat = Catalog(self.db_path, restore_active=True)
            try:
                if cat.set_active_target(target_id):
                    self.app.sub_title = D.clip(cat.target() or "catalog", 48)
                    self._set_brand()
                    self.action_reload()
            finally:
                cat.close()

        def action_back(self) -> None:
            # Never pop an active live screen: doing so would orphan its
            # Playwright worker. Signal a safe stop first; the user can quit
            # or navigate after the capture reaches its terminal state.
            if self.live and not self._done:
                self.action_stop_capture()
                return
            # Pop back to the home screen if we came from it; otherwise ask
            # before closing so Esc never bypasses graceful shutdown.
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            else:
                self.action_confirm_quit()

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
        QuitConfirmScreen { align: center middle; background: $background 80%; }
        QuitConfirmScreen #quit-dialog { width: 58; height: auto; padding: 2 3; border: round $error; background: $surface; }
        TargetPickerScreen { align: center middle; background: $background 80%; }
        TargetPickerScreen #target-dialog { width: 72; max-height: 80%; height: auto; padding: 2 3; border: round $primary; background: $surface; }
        .dialog-title { text-style: bold; color: $primary; margin: 0 0 1 0; }
        .dialog-copy { color: $text-muted; margin: 0 0 1 0; }
        .dialog-actions { height: auto; align: right middle; margin: 1 0 0 0; }
        .dialog-actions Button { margin-left: 1; }
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
            self._shutdown_requested = False
            self._background = []

        def start_background(self, fn, *, name: str):
            """Run a thread worker and retain a completion event for shutdown."""
            complete = threading.Event()

            def wrapped():
                try:
                    return fn()
                finally:
                    complete.set()

            worker = self.run_worker(wrapped, thread=True, name=name)
            self._background.append((worker, complete))
            return worker

        def has_active_workers(self) -> bool:
            return any(not complete.is_set() for _, complete in self._background)

        def request_shutdown(self) -> None:
            """Cancel pending workers and exit only after their bodies finish."""
            if self._shutdown_requested:
                return
            self._shutdown_requested = True
            # A live browser worker cannot receive KeyboardInterrupt from the
            # Textual UI. Signal it before waiting; attach mode detaches while
            # launch fallback closes the browser it owns.
            for screen in self.screen_stack:
                stop_event = getattr(screen, "_stop_event", None)
                if stop_event is not None:
                    stop_event.set()
            # The confirmation modal is dismissed before its callback runs,
            # so put the status on the app chrome as well as the dialog when
            # it is still mounted. The app remains visible while uncancellable
            # Python workers finish their SQLite/Playwright work.
            self.title = "GLYPH · finishing active work…"
            self.sub_title = "Please wait — closing safely"
            try:
                self.screen.query_one("#quit-copy", Static).update(
                    "Finishing active work… Glyph will close when it is safe.")
                for button in self.screen.query("#quit-dialog Button"):
                    button.disabled = True
            except Exception:
                pass
            # Textual cannot forcibly stop Python threads. Do not call
            # Worker.cancel(): it could prevent a not-yet-started wrapper from
            # setting its completion event. Waiting for the tracked bodies is
            # the graceful, SQLite-safe shutdown contract.
            self.run_worker(self._wait_for_shutdown, thread=True, name="shutdown")

        def _wait_for_shutdown(self) -> None:
            while any(not complete.is_set() for _, complete in self._background):
                time.sleep(0.05)
            self.call_from_thread(self._finish_shutdown)

        def _finish_shutdown(self) -> None:
            self.title = "GLYPH"
            self.sub_title = "closed safely"
            self.exit()

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
