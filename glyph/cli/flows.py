"""`glyph flows` — the captured network requests, as a table."""
from __future__ import annotations

import argparse

from glyph.cli import _console as C
from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
    sp = with_json(with_db(sub.add_parser("flows", help="list captured requests")))
    sp.add_argument("--filter", default=None,
                    help="substring match on method/URL")
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.tui import data as D
    cat = catalog(args, restore_active=True)
    try:
        headers, rows = D.flow_rows(cat, text_filter=args.filter)
    finally:
        cat.close()
    if args.json:
        emit([dict(zip(headers, r)) for r in rows], True)
        return 0
    C.print_rows(f"Flows  ·  [bold]{len(rows)}[/]", headers, rows, cyan_cols=(5,))
    return 0
