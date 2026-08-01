"""`glyph catalog` — summarize the catalog."""
from __future__ import annotations

import argparse

from glyph.cli._output import emit, human
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
    with_json(with_db(sub.add_parser("catalog", help="summarize the catalog"))
              ).set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    cat = catalog(args, restore_active=True)
    try:
        summary = cat.summary()
        endpoints = cat.endpoints()
    finally:
        cat.close()
    if args.json:
        emit({"summary": summary, "endpoints": [e.key for e in endpoints]}, True)
        return 0
    print(human(summary))
    print("endpoints:")
    for e in endpoints:
        note = "" if e.reachability == "direct" else f"  [{e.reachability}]"
        print(f"  {e.key}{note}")
    return 0
