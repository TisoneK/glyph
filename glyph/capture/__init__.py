"""Capture stage — get a target's observed traffic into the catalog.

- :func:`~glyph.capture.har.ingest_har` — dependency-free HAR ingestion.
- :func:`~glyph.capture.snapshot.harvest_labels` — HTML -> UI labels.
- ``mitm`` / ``driver`` — optional live backends (need the ``live`` extra).

The live backends are intentionally *not* imported here so that
``import glyph.capture`` never requires mitmproxy or Playwright.
"""
from __future__ import annotations

from glyph.capture.har import ingest_har
from glyph.capture.snapshot import harvest_labels, plain_text


def capture_live(*args, **kwargs):
    """Live browser capture — thin re-export of :func:`driver.capture_url`.

    Imported lazily so the base package never requires Playwright at load
    time (the driver only needs it when actually called).
    """
    from glyph.capture.driver import capture_url
    return capture_url(*args, **kwargs)


__all__ = ["ingest_har", "harvest_labels", "plain_text", "capture_live"]
