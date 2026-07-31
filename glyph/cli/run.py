"""`glyph run har|live` — capture, then schema -> rosetta -> sensitive."""
from __future__ import annotations

import argparse

from glyph.cli._format import sev_line
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
    print(f"schema:    {sch['fields']} fields, {sch['enum_candidates']} enum candidate(s)")
    print(f"rosetta:   {ros['entries']} decoded "
          f"({ros['high_confidence']} high-confidence, {ros['needs_review']} to review)")
    hint = "'glyph dict' to view"
    if not getattr(args, "no_sensitive", False):
        from glyph.sensitive import run_scan
        sens = run_scan(cat)
        line = (f"sensitive: {sens['actionable_total']} finding(s) "
                f"({sev_line(sens.get('actionable_by_severity', {}))})")
        noise = sens.get("tracking_noise", 0)
        if noise:
            line += f", +{noise} tracking/ad noise"
        print(line)
        hint += ", 'glyph sensitive' for findings"
    print(f"\nCatalog: {args.db}  —  {hint}, 'glyph codegen' to export.")


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
