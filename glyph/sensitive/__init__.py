"""Sensitive stage — flag sensitive data, sensitive endpoints, and risk.

Passive analysis over the captured catalog, for authorized assessment. It
FLAGS and LOCATES; it never removes the values it finds (redaction is an
opt-in export concern, not a default) and never actively probes a target.

    from glyph.sensitive import run_scan
    run_scan(catalog)          # writes findings to the catalog
    catalog.findings(min_severity="high")
"""
from __future__ import annotations

from glyph.sensitive.detectors import mask, scan_value
from glyph.sensitive.scan import run_scan, scan_data, summarize

__all__ = ["run_scan", "scan_data", "summarize", "scan_value", "mask"]
