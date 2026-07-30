"""Schema stage — infer per-endpoint structure and flag enum candidates."""
from __future__ import annotations

from glyph.schema.infer import build_schema, infer_all, infer_endpoint

__all__ = ["infer_all", "infer_endpoint", "build_schema"]
