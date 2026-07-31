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
    sub = p.add_subparsers(dest="command", required=True)
    for module in _COMMANDS:
        module.add_parser(sub)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


__all__ = ["main", "build_parser"]
