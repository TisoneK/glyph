"""Formatting helpers — severity summary lines, value masking, tables.

Presentation only; shared across `sensitive`, `dict`, `schema` output so
they look consistent (ADR-5).
"""
from __future__ import annotations

from typing import Dict, List, Sequence


def sev_line(sev: Dict[str, int]) -> str:
    """'2 high, 5 medium' from a {severity: count} map (severe first)."""
    order = ("critical", "high", "medium", "low")
    return ", ".join(f"{sev[s]} {s}" for s in order if sev.get(s)) or "none"


def mask_value(value, keep: int = 4) -> str:
    """Mask a value for display — enough to identify, not to leak.

    ``sk_live_5fa2...` -> ``sk_l***xdEf`` (prefix + last chars). Short
    values are mostly starred. Never mutates stored data.
    """
    if value is None:
        return ""
    v = str(value)
    if len(v) <= 2:
        return "*" * len(v)
    if len(v) <= keep * 2:
        return v[:2] + "*" * (len(v) - 2)
    return f"{v[:keep]}***{v[-keep:]}"


def table(rows: Sequence[Sequence[str]], headers: Sequence[str]) -> str:
    """Render a simple fixed-width table (stdlib only, no deps)."""
    cols = list(zip(*([headers] + [list(r) for r in rows]))) if rows else [
        [h] for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    out = [line, "  ".join("-" * w for w in widths)]
    for r in rows:
        out.append("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))
    return "\n".join(out)
