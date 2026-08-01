"""`glyph schema` — infer fields and flag enum candidates."""
from __future__ import annotations

import argparse

from glyph.cli._shared import catalog, with_db


def add_parser(sub) -> None:
    with_db(sub.add_parser("schema", help="infer fields + enum candidates")
            ).set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.schema import infer_all
    cat = catalog(args, restore_active=True)
    try:
        res = infer_all(cat)
    finally:
        cat.close()
    print(f"Inferred {res['fields']} fields across {res['endpoints']} "
          f"endpoints; {res['enum_candidates']} enum candidate(s)")
    return 0
