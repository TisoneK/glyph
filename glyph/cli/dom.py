"""`glyph dom` — the harvested DOM elements/labels, as a table."""
from __future__ import annotations

import argparse

from glyph.cli import _console as C
from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
    with_json(with_db(sub.add_parser("dom", help="list harvested DOM elements"))
              ).set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.tui import data as D
    cat = catalog(args, restore_active=True)
    try:
        headers, rows = D.dom_rows(cat)
    finally:
        cat.close()
    if args.json:
        emit([dict(zip(headers, r)) for r in rows], True)
        return 0
    C.print_rows(f"DOM elements  ·  [bold]{len(rows)}[/]", headers, rows,
                 cyan_cols=(1,))
    return 0
