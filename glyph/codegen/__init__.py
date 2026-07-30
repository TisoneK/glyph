"""Codegen stage — emit an OpenAPI 3 spec (enums annotated with meanings)."""
from __future__ import annotations

from glyph.codegen.openapi import to_openapi, to_openapi_json

__all__ = ["to_openapi", "to_openapi_json"]
