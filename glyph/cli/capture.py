"""`glyph capture har|live` — get observed traffic into the catalog."""
from __future__ import annotations

import argparse
import sys

from glyph.cli._shared import (
    catalog,
    live_kwargs,
    report_live,
    with_db,
    with_live,
)


def _progress(msg: str) -> None:
    """Live progress to stderr (TTY only) so the terminal shows activity.
    A live capture takes 30s+ with Playwright; without this it looks frozen."""
    if sys.stderr.isatty():
        print(f"  {msg}", file=sys.stderr, flush=True)


def add_parser(sub) -> None:
    sp = with_db(sub.add_parser("capture", help="ingest traffic"))
    csub = sp.add_subparsers(dest="capture_kind", required=True)
    har = with_db(csub.add_parser("har", help="ingest a HAR file"))
    har.add_argument("file")
    har.add_argument("--no-html", action="store_true",
                     help="skip harvesting labels from HTML responses")
    har.set_defaults(func=run_har)
    live = with_live(with_db(csub.add_parser(
        "live", help="drive a live page and capture everything (any site)")))
    live.set_defaults(func=run_live)


def run_har(args: argparse.Namespace) -> int:
    from glyph.capture import ingest_har
    _progress(f"ingesting HAR: {args.file}")
    cat = catalog(args)
    try:
        res = ingest_har(cat, args.file, harvest_html=not args.no_html)
    finally:
        cat.close()
    print(f"Ingested {res['flows']} flows, {res['pages']} page(s) "
          f"from {args.file}")
    return 0


def run_live(args: argparse.Namespace) -> int:
    from glyph.capture import capture_live
    _progress(f"launching browser → {args.url}")
    _progress("(driving the page; capturing flows as they load…)")
    cat = catalog(args)
    try:
        res = capture_live(cat, args.url, **live_kwargs(args))
    finally:
        cat.close()
    _progress(f"captured {res.get('flows', 0)} flows — done")
    report_live(args.url, res)
    return 0
