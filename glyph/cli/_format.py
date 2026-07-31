"""Formatting helpers — color, severity styling, value masking, tables.

Presentation only, shared so `sensitive`, `dict`, `run`, and the analyzer
commands look like one tool. Color is TTY-aware: disabled when stdout is
not a terminal, when ``NO_COLOR`` is set, or under ``--json`` — so pipes,
files, and tests stay plain (ADR-5).
"""
from __future__ import annotations

import os
import re
import sys
from typing import Dict, Sequence

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_CODES = {
    "reset": "0", "bold": "1", "dim": "2",
    "red": "31", "green": "32", "yellow": "33", "blue": "34",
    "magenta": "35", "cyan": "36", "bright_red": "91", "gray": "90",
}
_SEV_STYLE = {
    "critical": ("bright_red", "bold"),
    "high": ("red",),
    "medium": ("yellow",),
    "low": ("gray",),
}


def use_color() -> bool:
    return (sys.stdout.isatty()
            and os.environ.get("NO_COLOR") is None
            and os.environ.get("TERM") != "dumb")


def style(text, *names: str) -> str:
    """Wrap ``text`` in ANSI styles (no-op when color is off)."""
    if not names or not use_color():
        return str(text)
    codes = ";".join(_CODES[n] for n in names)
    return f"\x1b[{codes}m{text}\x1b[0m"


def _vlen(s) -> int:
    """Visible length, ignoring ANSI escapes (for table alignment)."""
    return len(_ANSI.sub("", str(s)))


def sev_label(sev: str, width: int = 0) -> str:
    """A color-coded, optionally width-padded severity label."""
    txt = (sev or "").upper()
    if width:
        txt = txt.ljust(width)
    return style(txt, *_SEV_STYLE.get((sev or "").lower(), ("gray",)))


def sev_line(sev: Dict[str, int]) -> str:
    """'2 high, 5 medium' (severe first), each count colored by severity."""
    order = ("critical", "high", "medium", "low")
    parts = [style(f"{sev[s]} {s}", *_SEV_STYLE[s]) for s in order if sev.get(s)]
    return ", ".join(parts) or style("none", "gray")


def mask_value(value, keep: int = 4) -> str:
    """Mask a value for display — enough to identify, not to leak."""
    if value is None:
        return ""
    v = str(value)
    if len(v) <= 2:
        return "*" * len(v)
    if len(v) <= keep * 2:
        return v[:2] + "*" * (len(v) - 2)
    return f"{v[:keep]}***{v[-keep:]}"


def table(rows: Sequence[Sequence[str]], headers: Sequence[str]) -> str:
    """Render an aligned table; ANSI-aware so colored cells still line up."""
    grid = [list(headers)] + [list(r) for r in rows]
    widths = [max(_vlen(row[i]) for row in grid) for i in range(len(headers))]

    def cell(c, w: int) -> str:
        return str(c) + " " * (w - _vlen(c))

    out = ["  ".join(style(cell(h, w), "bold") for h, w in zip(headers, widths)),
           "  ".join(style("─" * w, "gray") for w in widths)]
    for r in rows:
        out.append("  ".join(cell(c, w) for c, w in zip(r, widths)))
    return "\n".join(out)


def label(text: str) -> str:
    """A bold key/label (for summary lines and tree keys)."""
    return style(text, "bold")
