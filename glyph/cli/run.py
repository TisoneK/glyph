"""`glyph run har|live` — capture, then schema -> rosetta -> sensitive."""
from __future__ import annotations

import argparse

from glyph.cli import _console as C
from glyph.cli._format import num, sev_line, style
from glyph.cli._shared import (
    catalog,
    live_kwargs,
    with_db,
    with_live,
)

_LABELW = 10


def _row(key: str, value: str) -> str:
    return f"  {style(key.ljust(_LABELW), 'bold', 'cyan')} {value}"


def _sub(text: str) -> str:
    return f"  {' ' * _LABELW} {style(text, 'gray')}"


def add_parser(sub) -> None:
    sp = with_db(sub.add_parser(
        "run", help="capture -> schema -> rosetta -> sensitive"))
    rsub = sp.add_subparsers(dest="run_kind", required=True)
    rhar = with_db(rsub.add_parser("har", help="run the pipeline on a HAR file"))
    rhar.add_argument("file")
    rhar.add_argument("--no-html", action="store_true")
    rhar.add_argument("--no-sensitive", action="store_true",
                      help="skip the sensitive/risk scan")
    rhar.set_defaults(func=run_har)
    rlive = with_live(with_db(rsub.add_parser(
        "live", help="live-capture a page, then open the dashboard")))
    rlive.add_argument("--no-sensitive", action="store_true",
                       help="skip the sensitive/risk scan")
    rlive.add_argument("--no-tui", action="store_true",
                       help="print the summary instead of opening the dashboard")
    rlive.set_defaults(func=run_live)


def _types_line(cap: dict) -> str:
    types = {k.split(":")[-1]: v for k, v in (cap.get("by_source") or {}).items()}
    prio = ["xhr", "fetch", "websocket", "document"]
    parts = [f"{t}={types[t]}" for t in prio if t in types]
    parts += [f"{t}={n}" for t, n in sorted(types.items()) if t not in prio]
    return " · ".join(parts[:9])


def _gather(cat, args, cap: dict) -> dict:
    from glyph.schema import infer_all
    from glyph.rosetta import build_dictionary
    d = {"cap": cap, "sch": infer_all(cat), "ros": build_dictionary(cat),
         "sens": None}
    if not getattr(args, "no_sensitive", False):
        from glyph.sensitive import run_scan
        d["sens"] = run_scan(cat)
    return d


def _render(args, header: str, r: dict) -> None:
    """Render the pipeline as one designed block (rich panel or plain)."""
    if C.HAS_RICH:
        _print_rich(args, header, r)
    else:
        _print_plain(args, header, r)


def _open_dashboard(args) -> bool:
    """Open the TUI dashboard when interactive + textual present. Returns
    True if it took over the screen (so we skip the printed summary)."""
    import sys
    if getattr(args, "no_tui", False) or not sys.stdout.isatty():
        return False
    try:
        from glyph.tui import HAS_TEXTUAL, run_dashboard
    except Exception:
        return False
    if not HAS_TEXTUAL:
        return False
    run_dashboard(args.db)
    return True


def _cap_value(cap: dict) -> str:
    v = f"{cap['flows']} flows"
    if cap.get("labels") is not None:
        v += f" · {cap['labels']} DOM labels"
    elif cap.get("pages") is not None:
        v += f" · {cap['pages']} page(s)"
    return v


def _print_rich(args, header: str, r: dict) -> None:
    from rich import box
    from rich.panel import Panel
    from rich.table import Table
    con = C.con()
    cap, sch, ros, sens = r["cap"], r["sch"], r["ros"], r["sens"]

    g = Table.grid(padding=(0, 3))
    g.add_column(style="bold cyan", justify="left")
    g.add_column()
    g.add_row("capture", f"[bold]{cap['flows']}[/] flows"
              + (f" · [bold]{cap['labels']}[/] DOM labels"
                 if cap.get("labels") is not None else
                 f" · {cap['pages']} page(s)" if cap.get("pages") is not None else ""))
    if cap.get("by_source"):
        g.add_row("", f"[grey58]{_types_line(cap)}[/]")
    if cap.get("error"):
        g.add_row("", f"[yellow]note: {cap['error']}[/]")
    g.add_row("schema", f"[bold]{sch['fields']}[/] fields · "
                        f"{sch['enum_candidates']} enum candidates")
    g.add_row("rosetta", f"[bold]{ros['entries']}[/] decoded · "
                         f"{ros['high_confidence']} high-confidence · "
                         f"{ros['needs_review']} to review")
    steps = ["glyph dict", "glyph codegen"]
    if sens is not None:
        val = f"[bold]{sens['actionable_total']}[/] findings"
        if sens["actionable_total"]:
            val += f" · {C.sev_counts(sens.get('actionable_by_severity', {}))}"
        noise = sens.get("tracking_noise", 0)
        if noise:
            val += f"   [grey58](+{noise} tracking noise · --all)[/]"
        g.add_row("sensitive", val)
        steps.insert(1, "glyph sensitive")

    con.print(Panel(g, title=f"[bold]{header}[/]", title_align="left",
                    border_style="cyan", box=box.ROUNDED, padding=(1, 2)))
    con.print(f"  [bold cyan]view[/]   [grey58]{' · '.join(steps)}[/]")
    con.print(f"  [grey58]catalog: {args.db}[/]")


def _print_plain(args, header: str, r: dict) -> None:
    cap, sch, ros, sens = r["cap"], r["sch"], r["ros"], r["sens"]
    print()
    print(f"  {style(header, 'bold')}\n")
    print(_row("capture", _cap_value(cap)))
    if cap.get("by_source"):
        print(_sub(_types_line(cap)))
    print(_row("schema", f"{num(sch['fields'])} fields · "
                         f"{sch['enum_candidates']} enum candidates"))
    print(_row("rosetta", f"{num(ros['entries'])} decoded · "
                          f"{ros['high_confidence']} high-confidence · "
                          f"{ros['needs_review']} to review"))
    steps = ["glyph dict", "glyph codegen"]
    if sens is not None:
        val = f"{num(sens['actionable_total'])} findings"
        if sens["actionable_total"]:
            val += f" · {sev_line(sens.get('actionable_by_severity', {}))}"
        print(_row("sensitive", val))
        steps.insert(1, "glyph sensitive")
    print(f"\n  {style('view', 'bold', 'cyan')}"
          + " " * (_LABELW - 4) + style(" · ".join(steps), "gray"))
    print(_sub(f"catalog: {args.db}"))


def run_har(args: argparse.Namespace) -> int:
    from glyph.capture import ingest_har
    cat = catalog(args)
    try:
        cap = ingest_har(cat, args.file, harvest_html=not args.no_html)
        r = _gather(cat, args, cap)
    finally:
        cat.close()
    _render(args, args.file, r)
    return 0


def run_live(args: argparse.Namespace) -> int:
    from glyph.capture import capture_live
    cat = catalog(args)
    try:
        cap = capture_live(cat, args.url, **live_kwargs(args))
        r = _gather(cat, args, cap)
    finally:
        cat.close()
    # Leave the user inside the interactive dashboard (ADR-9); fall back to
    # the printed summary in a pipe/CI or with --no-tui / no textual.
    if not _open_dashboard(args):
        _render(args, args.url, r)
    return 0
