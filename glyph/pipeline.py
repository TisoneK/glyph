"""Parallel analysis pipeline with a coordinated SNI-hunt lifecycle.

The core stages have one dependency edge: schema inference must complete
before Rosetta decoding. Sensitive scanning is independent, so the core runs
those two lanes concurrently. SNI hunting is independently target-pinned and
runs beside the core through :func:`run_pipeline`; the lower-level
:func:`run_snihunt` remains available when callers need only that stage.
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

    Returns ``{sch, ros, sens, sni}``; ``sni`` is ``None`` here to preserve
    the renderer result shape. Use :func:`run_pipeline` when SNI should run
    concurrently with these core lanes.
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
        from glyph.rosetta import build_dictionary
        from glyph.schema import infer_all
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


def run_pipeline(db_path: str, *, target: Optional[str] = None,
                  no_schema: bool = False,
                  no_rosetta: bool = False,
                  no_sensitive: bool = False,
                  no_snihunt: bool = False,
                  snihunt_no_net: bool = False,
                  progress: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Run core analysis and SNI hunting concurrently.

    ``run_analysis`` owns the schema→Rosetta and sensitive lanes, while
    ``run_snihunt`` owns its own target-pinned catalog connection. Keeping the
    two jobs in separate futures lets slow network recon overlap the local
    analysis without sharing sqlite connections or allowing one stage to
    redirect another stage's writes.
    """
    lock = threading.Lock()

    def _prog(message: str) -> None:
        if progress is None:
            return
        with lock:
            try:
                progress(message)
            except Exception:
                pass

    with ThreadPoolExecutor(max_workers=2 if not no_snihunt else 1) as ex:
        analysis_future = ex.submit(
            run_analysis,
            db_path,
            target=target,
            no_schema=no_schema,
            no_rosetta=no_rosetta,
            no_sensitive=no_sensitive,
            progress=_prog,
        )
        sni_future = None
        if not no_snihunt:
            sni_future = ex.submit(
                run_snihunt,
                db_path,
                target=target,
                snihunt_no_net=snihunt_no_net,
                progress=_prog,
            )
        result = analysis_future.result()
        if sni_future is not None:
            result.update(sni_future.result())
    return result


def run_snihunt(db_path: str, *, target: Optional[str] = None,
                snihunt_no_net: bool = False,
                progress: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Run SNI hunting in its own target-pinned catalog lifecycle.

    ``run_pipeline`` submits this function beside the core pool. Keeping it
    independently callable is useful for a focused SNI rerun and preserves
    the explicit target boundary against later UI target switches.
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
