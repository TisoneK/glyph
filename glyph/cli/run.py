"""`glyph run har|live` — capture, then schema -> rosetta -> sensitive."""
from __future__ import annotations

import argparse

from glyph.cli._format import label, sev_line, style
from glyph.cli._shared import (
    catalog,
    live_kwargs,
    report_live,
    with_db,
    with_live,
)


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


def _analyze_and_report(cat, args) -> None:
    """Shared tail: schema -> rosetta -> (sensitive) + summary. Sensitive runs
    by default (passive, over already-captured data); skip with --no-sensitive."""
    from glyph.schema import infer_all
    from glyph.rosetta import build_dictionary
    sch = infer_all(cat)
    ros = build_dictionary(cat)
    print(f"{label('schema:   ')} {sch['fields']} fields, "
          f"{sch['enum_candidates']} enum candidate(s)")
    print(f"{label('rosetta:  ')} {ros['entries']} decoded "
          f"({ros['high_confidence']} high-confidence, {ros['needs_review']} to review)")
    hint = "'glyph dict' to view"
    if not getattr(args, "no_sensitive", False):
        from glyph.sensitive import run_scan
        sens = run_scan(cat)
        line = (f"{label('sensitive:')} {sens['actionable_total']} finding(s) "
                f"({sev_line(sens.get('actionable_by_severity', {}))})")
        noise = sens.get("tracking_noise", 0)
        if noise:
            line += style(f", +{noise} tracking/ad noise", "gray")
        print(line)
        hint += ", 'glyph sensitive' for findings"
    tail = style(f"—  {hint}, 'glyph codegen' to export.", "gray")
    print(f"\n{label('Catalog:')} {args.db}  {tail}")


def run_har(args: argparse.Namespace) -> int:
    from glyph.capture import ingest_har
    cat = catalog(args)
    try:
        cap = ingest_har(cat, args.file, harvest_html=not args.no_html)
        print(f"capture:   {cap['flows']} flows, {cap['pages']} page(s)")
        _analyze_and_report(cat, args)
    finally:
        cat.close()
    return 0


def run_live(args: argparse.Namespace) -> int:
    from glyph.capture import capture_live
    cat = catalog(args)
    try:
        cap = capture_live(cat, args.url, **live_kwargs(args))
        report_live(args.url, cap)
        _analyze_and_report(cat, args)
    finally:
        cat.close()
    return 0
