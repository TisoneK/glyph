"""Glyph TUI — an interactive dashboard over the catalog (optional `tui` extra).

Presentation/interaction only: `glyph.tui.data` provides pure catalog views,
`glyph.tui.app` is the Textual app. The analysis engine stays headless.
"""
from __future__ import annotations

from glyph.tui.app import HAS_TEXTUAL, run_dashboard

__all__ = ["run_dashboard", "HAS_TEXTUAL"]
