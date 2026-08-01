"""The GLYPH wordmark — a stylised ANSI-shadow banner for the home screen."""
from __future__ import annotations

BANNER = r"""
 ██████╗ ██╗     ██╗   ██╗██████╗ ██╗  ██╗
██╔════╝ ██║     ╚██╗ ██╔╝██╔══██╗██║  ██║
██║  ███╗██║      ╚████╔╝ ██████╔╝███████║
██║   ██║██║       ╚██╔╝  ██╔═══╝ ██╔══██║
╚██████╔╝███████╗   ██║   ██║     ██║  ██║
 ╚═════╝ ╚══════╝   ╚═╝   ╚═╝     ╚═╝  ╚═╝
""".strip("\n")

# Vertical cyan→indigo gradient, one shade per row.
_GRAD = ["#8be9fd", "#67d3f0", "#48bde3", "#37a2d4", "#2d84bd", "#2b64a6"]

TAGLINE = "decode any target's surface  ·  capture → schema → rosetta → sensitive"


def logo_renderable():
    """A rich Text of the banner with a vertical gradient (plain str fallback)."""
    try:
        from rich.text import Text
    except ImportError:  # pragma: no cover
        return BANNER
    t = Text(justify="left")
    lines = BANNER.splitlines()
    for i, line in enumerate(lines):
        t.append(line + ("\n" if i < len(lines) - 1 else ""),
                 style=f"bold {_GRAD[min(i, len(_GRAD) - 1)]}")
    return t


def logo_compact():
    """A one-line gradient wordmark for the dashboard header — the full
    banner is too tall to share the output page with the tables, so the
    dashboard inherits the same gradient in a single row."""
    from rich.text import Text
    t = Text()
    t.append("◈ ", style=f"bold {_GRAD[2]}")
    for i, ch in enumerate("GLYPH"):
        t.append(ch, style=f"bold {_GRAD[i % len(_GRAD)]}")
    return t
