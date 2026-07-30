"""Rosetta — decode opaque API codes into meaning (the centrepiece).

``build_dictionary(catalog)`` runs the correlation strategies and writes a
code -> meaning dictionary with confidence scores into the catalog.
"""
from __future__ import annotations

from glyph.rosetta.dictionary import build_dictionary, collect_candidates

__all__ = ["build_dictionary", "collect_candidates"]
