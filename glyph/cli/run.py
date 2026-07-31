"""`glyph run har|live` — capture, then schema -> rosetta -> sensitive."""
from __future__ import annotations

import argparse

from glyph.cli._format import label, num, sev_line, style
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
        "live", help="live-capture a page, then schema + rosetta + sensitive")))
    rlive.add_argument("--no-sensitive", action="store_true",
                       help="skip the sensitive/risk scan")
    rlive.set_defaults(func=run_live)


def _print_summary(cat, args, header: str, cap: dict) -> None:
    """Render the whole pipeline as one clean, aligned block. Sensitive runs
    by default (passive, over already-captured data); skip with --no-sensitive."""
    from glyph.schema import infer_all
    from glyph.rosetta import build_dictionary
    sch = infer_all(cat)
    ros = build_dictionary(cat)

    print()
    print(f"  {style(header, 'bold')}")
    print()

    # capture
    cap_val = f"{num(cap['flows'])} flows"
    if cap.get("labels") is not None:
        cap_val += f" · {cap['labels']} DOM labels"
    elif cap.get("pages") is not None:
        cap_val += f" · {cap['pages']} page(s)"
    print(_row("capture", cap_val))
    if cap.get("by_source"):
        types = {k.split(":")[-1]: v for k, v in cap["by_source"].items()}
        prio = ["xhr", "fetch", "websocket", "document"]
        parts = [f"{t}={types[t]}" for t in prio if t in types]
        parts += [f"{t}={n}" for t, n in sorted(types.items()) if t not in prio]
        print(_sub(" · ".join(parts[:9])))
    if cap.get("error"):
        print(f"  {' ' * _LABELW} {style('note: ' + str(cap['error']), 'yellow')}")

    print(_row("schema", f"{num(sch['fields'])} fields · "
                         f"{sch['enum_candidates']} enum candidates"))
    print(_row("rosetta", f"{num(ros['entries'])} decoded · "
                          f"{ros['high_confidence']} high-confidence · "
                          f"{ros['needs_review']} to review"))

    steps = ["glyph dict", "glyph codegen"]
    if not getattr(args, "no_sensitive", False):
        from glyph.sensitive import run_scan
        sens = run_scan(cat)
        val = f"{num(sens['actionable_total'])} findings"
        sl = sev_line(sens.get("actionable_by_severity", {}))
        if sens["actionable_total"]:
            val += f" · {sl}"
        noise = sens.get("tracking_noise", 0)
        if noise:
            val += style(f" · +{noise} tracking noise (--all)", "gray")
        print(_row("sensitive", val))
        steps.insert(1, "glyph sensitive")

    print()
    print(f"  {style('view', 'bold', 'cyan')}"
          + " " * (_LABELW - 4)
          + style(" · ".join(steps), "gray"))
    print(_sub(f"catalog: {args.db}"))
    print()


def run_har(args: argparse.Namespace) -> int:
    from glyph.capture import ingest_har
    cat = catalog(args)
    try:
        cap = ingest_har(cat, args.file, harvest_html=not args.no_html)
        _print_summary(cat, args, args.file, cap)
    finally:
        cat.close()
    return 0


def run_live(args: argparse.Namespace) -> int:
    from glyph.capture import capture_live
    cat = catalog(args)
    try:
        cap = capture_live(cat, args.url, **live_kwargs(args))
        _print_summary(cat, args, args.url, cap)
    finally:
        cat.close()
    return 0
