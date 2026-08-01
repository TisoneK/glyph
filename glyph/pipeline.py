"""Parallel analysis pipeline — run the post-capture stages concurrently.

The four analysis stages have a real dependency graph, and only one edge:

    schema -> rosetta : rosetta's dom_attribute strategy reads the
                        enum-candidate fields that schema inference writes,
                        so rosetta must run AFTER schema (chained).
    sensitive         : independent of schema/rosetta (scans flows directly).
    snihunt           : independent of all three (reads the captured host
                        surface), and the slowest (bounded network recon).

So instead of the historical strictly-serial run (schema, then rosetta, then
sensitive, then snihunt — each waiting for the previous), :func:`run_analysis`
runs THREE LANES concurrently over a thread pool:

    lane 1: schema -> rosetta   (chained, one worker)
    lane 2: sensitive           (own worker)
    lane 3: snihunt             (own worker)

Why this is safe (ADR-15):

- The catalog is SQLite **WAL + busy_timeout=5000** (built for the TUI's
  concurrent capture/analyze writers), so multiple connections writing from
  different threads are supported.
- Each lane opens its OWN :class:`~glyph.catalog.Catalog` connection —
  sqlite3 connections are bound to the creating thread.
- Each lane RE-ACTIVATES the target host first (:meth:`set_target`). A fresh
  Catalog has no active target; without this every write silently falls into
  the reserved ``(unassigned)`` bucket (id=0) — the bug that sent the TUI's
  analysis output off-target (Session 23: ``glyph target show`` reported
  fields/findings/dictionary = 0 while the dashboard displayed them).
- Findings writes are kind-scoped (``clear_findings(kind=...)`` per stage), so
  concurrent sensitive + snihunt lanes never wipe each other (Session 16 fix).

The shared entry point is used by BOTH the headless CLI (``glyph/cli/run.py``
``_gather``) and the live TUI (``glyph/tui/app.py`` ``_analyze_once`` /
``_finalize``), so the two surfaces behave identically.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from glyph.catalog import Catalog


def run_analysis(db_path: str, *, target: Optional[str] = None,
                 no_sensitive: bool = False,
                 no_snihunt: bool = False,
                 snihunt_no_net: bool = False,
                 progress: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Run the analysis stages concurrently. Returns ``{sch, ros, sens, sni}``.

    Parameters mirror the ``glyph run`` opt-out flags so the CLI and TUI can
    pass them straight through:

    - ``target`` — the active capture host. Every lane re-activates it so
      all writes land on the ACTIVE target, never the ``(unassigned)`` bucket.
    - ``no_sensitive`` — skip the sensitive/risk scan lane.
    - ``no_snihunt`` — skip the SNI bug-host hunt lane.
    - ``snihunt_no_net`` — hunt lane runs local heuristics only (no DoH / CT /
      reverse-IP outbound calls).
    - ``progress`` — ``progress(message)`` called from any lane; internally
      lock-guarded so concurrent lines never interleave mid-print.

    A lane exception propagates to the caller AFTER the pool drains (other
    lanes finish their writes first; a re-run is idempotent).
    """
    lock = threading.Lock()

    def _prog(msg: str) -> None:
        if progress is not None:
            with lock:
                try:
                    progress(msg)
                except Exception:
                    pass  # progress reporting must never break a lane

    def _open() -> Catalog:
        # restore_active=True (Session 26): a lane whose `target` is None
        # (e.g. TUI dashboard opened without a live URL) falls back to the
        # persisted CURRENT target instead of writing to the (unassigned)
        # bucket. An explicit `target` still overrides via set_target below.
        cat = Catalog(db_path, restore_active=True)
        if target:
            cat.set_target(target)
        return cat

    def _schema_rosetta() -> Dict[str, Any]:
        from glyph.schema import infer_all
        from glyph.rosetta import build_dictionary
        cat = _open()
        try:
            _prog("schema: inferring fields + enum candidates…")
            sch = infer_all(cat)
            _prog("rosetta: decoding…")
            ros = build_dictionary(cat)
            _prog(f"rosetta: decoded {ros['entries']} entries")
            return {"sch": sch, "ros": ros}
        finally:
            cat.close()

    def _sensitive() -> Dict[str, Any]:
        from glyph.sensitive import run_scan
        cat = _open()
        try:
            _prog("sensitive: scanning for PII / secrets / risk…")
            return {"sens": run_scan(cat)}
        finally:
            cat.close()

    def _snihunt() -> Dict[str, Any]:
        from glyph.snihunt import run_hunt
        cat = _open()
        try:
            if snihunt_no_net:
                _prog("snihunt: local heuristics only (--no-net)…")
            else:
                _prog("snihunt: reverse-IP + CT logs + CDN detection (network)…")
            return {"sni": run_hunt(cat, net=not snihunt_no_net, progress=_prog)}
        finally:
            cat.close()

    lanes = [_schema_rosetta]
    if not no_sensitive:
        lanes.append(_sensitive)
    if not no_snihunt:
        lanes.append(_snihunt)

    out: Dict[str, Any] = {"sch": None, "ros": None, "sens": None, "sni": None}
    with ThreadPoolExecutor(max_workers=len(lanes)) as ex:
        futures = [ex.submit(fn) for fn in lanes]
        for fut in futures:
            out.update(fut.result())  # first lane exception propagates here
    return out
