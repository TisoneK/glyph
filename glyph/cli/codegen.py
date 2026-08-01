"""`glyph codegen` — emit an OpenAPI 3 spec."""
from __future__ import annotations

import argparse

from glyph.cli._format import style
from glyph.cli._shared import catalog, with_db


def add_parser(sub) -> None:
    sp = with_db(sub.add_parser("codegen", help="emit OpenAPI 3"))
    sp.add_argument("--out", help="write spec to this file")
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.codegen import to_openapi_json
    cat = catalog(args, restore_active=True)
    try:
        spec = to_openapi_json(cat)
    finally:
        cat.close()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(spec)
        print(style(f"Wrote OpenAPI spec to {args.out}", "green"))
    else:
        print(spec)
    return 0
