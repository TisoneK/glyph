"""`glyph fingerprint` — identify the backend stack."""
from __future__ import annotations

import argparse

from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
    with_json(with_db(sub.add_parser("fingerprint", help="backend family"))
              ).set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.fingerprint import fingerprint
    cat = catalog(args)
    try:
        emit(fingerprint(cat), args.json)
    finally:
        cat.close()
    return 0
