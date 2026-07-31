"""Rich-backed console — the CLI's presentation layer.

Rich gives real tables/panels and cross-platform color (incl. Windows) and
auto-degrades to plain text when output is piped, ``NO_COLOR`` is set, or a
terminal isn't attached. Imported only by the CLI, so ``import glyph`` (the
library) never needs it; if rich is somehow absent, ``HAS_RICH`` is False
and callers fall back to plain rendering.
"""
from __future__ import annotations

from typing import Optional

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:  # pragma: no cover
    HAS_RICH = False

# Severity -> rich style. Kept in one place so every table/summary agrees.
SEV_STYLE = {
    "critical": "bold bright_red",
    "high": "red",
    "medium": "yellow",
    "low": "grey58",
}
_console: Optional["Console"] = None


def con() -> "Console":
    """The shared Console (lazily built)."""
    global _console
    if _console is None:
        _console = Console(highlight=False)
    return _console


def sev_cell(severity: str):
    """A severity label as a styled rich Text (or plain str without rich)."""
    txt = (severity or "").upper()
    if not HAS_RICH:
        return txt
    return Text(txt, style=SEV_STYLE.get((severity or "").lower(), "grey58"))


def sev_counts(by_sev: dict) -> str:
    """'4 high · 2 medium' with rich markup (severe first)."""
    order = ("critical", "high", "medium", "low")
    if not HAS_RICH:
        return ", ".join(f"{by_sev[s]} {s}" for s in order if by_sev.get(s)) or "none"
    parts = [f"[{SEV_STYLE[s]}]{by_sev[s]} {s}[/]" for s in order if by_sev.get(s)]
    return " · ".join(parts) or "[grey58]none[/]"


def table(title: Optional[str] = None) -> "Table":
    """A consistently-styled findings/data table."""
    return Table(
        title=title, title_justify="left", box=box.SIMPLE_HEAVY,
        header_style="bold", title_style="bold", expand=False,
        pad_edge=False, border_style="grey37",
    )


def print_rows(title, headers, rows, cyan_cols=()) -> None:
    """Render a (headers, rows) view as a table (rich, or plain fallback)."""
    if not HAS_RICH:
        from glyph.cli._format import table as plain_table
        print(title)
        print(plain_table(rows, headers))
        return
    t = table(title=title)
    for i, h in enumerate(headers):
        t.add_column(h, style="cyan" if i in cyan_cols else None,
                     no_wrap=(h in ("URL", "HOST", "PATH", "VALUE")))
    for r in rows:
        t.add_row(*[str(c) for c in r])
    con().print(t)
