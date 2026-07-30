"""Interactive review session — walk pending rows and decide each.

IO is injected (``input_fn`` / ``output_fn``) so the loop is testable
without a real terminal. The CLI wires in the builtins.
"""
from __future__ import annotations

from typing import Callable, Dict

from glyph.catalog import Catalog
from glyph.review.queue import confirm, edit, pending, reject, stats

_HELP = ("[c]onfirm  [e]dit <new meaning>  [r]eject  [s]kip  [q]uit")


def run_interactive(catalog: Catalog,
                    input_fn: Callable[[str], str] = input,
                    output_fn: Callable[[str], None] = print) -> Dict[str, int]:
    """Prompt for a decision on each pending row. Returns action counts."""
    rows = pending(catalog)
    actions = {"confirmed": 0, "edited": 0, "rejected": 0, "skipped": 0}
    if not rows:
        output_fn("Nothing to review — no pending rows.")
        return actions

    output_fn(f"{len(rows)} row(s) to review.  {_HELP}\n")
    for i, entry in enumerate(rows, 1):
        output_fn(f"[{i}/{len(rows)}] {entry.json_path}  {entry.code!r} -> "
                  f"{entry.meaning!r}")
        output_fn(f"      confidence {entry.confidence}  ({entry.strategy})")
        output_fn(f"      evidence: {entry.evidence}")
        try:
            raw = input_fn("  decision> ").strip()
        except EOFError:
            output_fn("\n(end of input — stopping)")
            break
        cmd = raw[:1].lower()
        if cmd == "q":
            break
        if cmd == "c":
            confirm(catalog, entry.id)
            actions["confirmed"] += 1
        elif cmd == "e":
            new_meaning = raw[1:].strip()
            if not new_meaning:
                new_meaning = input_fn("  new meaning> ").strip()
            if new_meaning:
                edit(catalog, entry.id, new_meaning)
                actions["edited"] += 1
            else:
                actions["skipped"] += 1
        elif cmd == "r":
            reject(catalog, entry.id)
            actions["rejected"] += 1
        else:
            actions["skipped"] += 1

    s = stats(catalog)
    output_fn(f"\nDone. This session: {actions}. "
              f"Catalog now: {s['confirmed']} confirmed, {s['edited']} edited, "
              f"{s['rejected']} rejected, {s['pending']} still pending.")
    return actions
