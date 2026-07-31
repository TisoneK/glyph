"""`glyph dashboard` — open the interactive TUI over a catalog."""
from __future__ import annotations

import argparse

from glyph.cli._shared import with_db


def add_parser(sub) -> None:
    with_db(sub.add_parser(
        "dashboard", help="open the interactive dashboard (TUI) over a catalog")
    ).set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.tui import run_dashboard  # raises RuntimeError if textual absent
    run_dashboard(args.db)
    return 0
