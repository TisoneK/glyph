"""Parallel core analysis pipeline with an independent SNI-hunt lifecycle.

The core stages have one dependency edge: schema inference must complete
before Rosetta decoding. Sensitive scanning is independent, so the core runs
those two lanes concurrently. SNI hunting is also independent, but it is
bounded network reconnaissance and is deliberately *not* part of the core
pool. Callers can await :func:`run_snihunt` (headless CLI) or submit it as a
separate worker (live TUI).
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from glyph.catalog import Catalog


def _open_catalog(db_path: str, target: Optional[str] = None) -> Catalog:
    """Open a target-pinned catalog connection for an analysis worker."""
    cat = Catalog(db_path, restore_active=True)
    if target:
        cat.set_target(target)
    return cat


def run_analysis(db_path: str, *, target: Optional[str] = None,
                 no_schema: bool = False,
                 no_rosetta: bool = False,
                 no_sensitive: bool = False,
                 progress: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Run schema/Rosetta and sensitive analysis concurrently.

    Returns ``{sch, ros, sens, sni}``; ``sni`` is always ``None`` here to
    preserve the renderer result shape. SNI work belongs to
    :func:`run_snihunt` now.
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
        return _open_catalog(db_path, target)

    def _schema_rosetta() -> Dict[str, Any]:
        # Rosetta depends on schema's enum-candidate fields, so these stay
        # chained inside one worker while the sensitive lane runs beside it.
        from glyph.schema import infer_all
        from glyph.rosetta import build_dictionary
        cat = _open()
        try:
            out: Dict[str, Any] = {}
            if not no_schema:
                _prog("schema: inferring fields + enum candidates…")
                out["sch"] = infer_all(cat)
            if not no_rosetta:
                _prog("rosetta: decoding…")
                ros = build_dictionary(cat)
                _prog(f"rosetta: decoded {ros['entries']} entries")
                out["ros"] = ros
            return out
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

    lanes: list = []
    if not (no_schema and no_rosetta):
        lanes.append(_schema_rosetta)
    if not no_sensitive:
        lanes.append(_sensitive)

    out: Dict[str, Any] = {"sch": None, "ros": None,
                           "sens": None, "sni": None}
    if not lanes:
        return out
    with ThreadPoolExecutor(max_workers=len(lanes)) as ex:
        futures = [ex.submit(fn) for fn in lanes]
        for fut in futures:
            out.update(fut.result())
    return out


def run_snihunt(db_path: str, *, target: Optional[str] = None,
                snihunt_no_net: bool = False,
                progress: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Run SNI hunting in its own catalog lifecycle.

    This function is intentionally not submitted to the core analysis pool.
    Its explicit target prevents a later UI target switch from redirecting
    findings to another target.
    """
    from glyph.snihunt import run_hunt

    lock = threading.Lock()

    def _prog(msg: str) -> None:
        if progress is not None:
            with lock:
                try:
                    progress(msg)
                except Exception:
                    pass

    cat = _open_catalog(db_path, target)
    try:
        if snihunt_no_net:
            _prog("snihunt: local heuristics only (--no-net)…")
        else:
            _prog("snihunt: reverse-IP + CT logs + CDN detection (network)…")
        return {"sni": run_hunt(cat, net=not snihunt_no_net, progress=_prog)}
    finally:
        cat.close()
