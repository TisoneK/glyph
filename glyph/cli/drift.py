"""`glyph drift` — diff two catalog snapshots."""
from __future__ import annotations

import argparse

from glyph.cli._output import emit
from glyph.cli._shared import with_json


def add_parser(sub) -> None:
    sp = with_json(sub.add_parser("drift", help="diff two catalogs"))
    sp.add_argument("before")
    sp.add_argument("after")
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.drift import diff_catalogs
    report = diff_catalogs(args.before, args.after)
    emit(report, args.json)
    return 0 if not report["has_drift"] else 2
