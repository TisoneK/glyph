"""`glyph auth` — classify authentication and request signing."""
from __future__ import annotations

import argparse

from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
    with_json(with_db(sub.add_parser("auth", help="auth + signing"))
              ).set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.auth import analyze
    cat = catalog(args)
    try:
        emit(analyze(cat), args.json)
    finally:
        cat.close()
    return 0
