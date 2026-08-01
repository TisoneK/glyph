"""`glyph rosetta` — decode opaque codes into meaning."""
from __future__ import annotations

import argparse

from glyph.cli._shared import catalog, with_db


def add_parser(sub) -> None:
    with_db(sub.add_parser("rosetta", help="decode codes -> meaning")
            ).set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.rosetta import build_dictionary
    cat = catalog(args, restore_active=True)
    try:
        res = build_dictionary(cat)
    finally:
        cat.close()
    print(f"Decoded {res['entries']} code(s): {res['high_confidence']} "
          f"high-confidence, {res['needs_review']} need review")
    return 0
