"""`glyph init` — create an empty catalog."""
from __future__ import annotations

import argparse

from glyph.cli._shared import catalog, with_db


def add_parser(sub) -> None:
    sp = with_db(sub.add_parser("init", help="create an empty catalog"))
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    catalog(args).close()
    print(f"Initialized catalog at {args.db}")
    return 0
