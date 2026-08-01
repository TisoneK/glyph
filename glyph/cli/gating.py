"""`glyph gating` — rate-limit and bot-management profiling."""
from __future__ import annotations

import argparse

from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
    with_json(with_db(sub.add_parser("gating", help="rate-limit + bot mgmt"))
              ).set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.gating import profile
    cat = catalog(args, restore_active=True)
    try:
        emit(profile(cat), args.json)
    finally:
        cat.close()
    return 0
