"""``glyph`` — the command-line entrypoint.

Presentation layer only: one module per subcommand (each exposes
``add_parser(sub)`` + ``run(args)``), with shared helpers in ``_shared``,
``_output``, and ``_format``. Business logic lives in the stage packages
(``glyph.rosetta``, ``glyph.sensitive``, …) — the single source of truth.
See ADR-5.
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from glyph import __version__
from glyph.cli import (
    auth,
    capture,
    catalog,
    codegen,
    dashboard,
    dict as dict_cmd,
    dom,
    drift,
    fingerprint,
    flows,
    gating,
    init,
    mobile,
    review,
    rosetta,
    run,
    schema,
    sensitive,
)
from glyph.cli._shared import live_kwargs as _live_kwargs  # re-export for tests

# Registration order = help-listing order.
_COMMANDS = [
    init, capture, run, dashboard,
    flows, dom, schema, rosetta, dict_cmd, sensitive, review,
    fingerprint, auth, gating, codegen, drift, mobile, catalog,
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="glyph",
        description="Capture, catalog, and decode a target's API surface.")
    p.add_argument("--version", action="version", version=f"glyph {__version__}")
    p.add_argument("--db", default="glyph.db",
                   help="catalog for the home screen (bare 'glyph')")
    sub = p.add_subparsers(dest="command", required=False)
    for module in _COMMANDS:
        module.add_parser(sub)
    return p


def _home_or_help(parser, args) -> int:
    """Bare `glyph`: open the home/splash TUI when interactive, else help."""
    import sys
    if sys.stdout.isatty():
        try:
            from glyph.tui import HAS_TEXTUAL, run_home
        except Exception:
            HAS_TEXTUAL = False
        if HAS_TEXTUAL:
            run_home(args.db)
            return 0
        print("The dashboard needs the 'tui' extra: pip install 'glyph-re[tui]'\n",
              file=sys.stderr)
    parser.print_help()
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "func", None) is None:
        return _home_or_help(parser, args)
    try:
        return args.func(args)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


__all__ = ["main", "build_parser"]
