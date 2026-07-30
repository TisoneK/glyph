"""Glyph — a general-purpose reverse-engineering toolkit.

Glyph turns a browsing/capture session against *any* target into a
documented, semantically-decoded catalog. It is domain-neutral: targets
are only *inputs* you point it at, never baked into the tool.

The pipeline is a set of composable stages over one shared catalog:

    capture  -> catalog -> schema -> rosetta -> (fingerprint, auth,
                                                 gating, codegen, drift, mobile)

- **capture**    ingest observed traffic (HAR today; live proxy/browser optional).
- **catalog**    the shared SQLite store every stage reads and writes.
- **schema**     infer a JSON Schema per endpoint and flag enum candidates.
- **rosetta**    the centrepiece — correlate opaque API codes with the
                 human-readable labels they map to, and emit a code->meaning
                 dictionary with confidence scores.
- **fingerprint** identify the backend family from response signals.
- **auth**       classify each endpoint's authentication / request-signing.
- **gating**     profile rate-limiting and bot-management signals.
- **codegen**    emit an OpenAPI 3 spec (enums annotated with meanings).
- **drift**      diff two catalog snapshots over time.
- **mobile**     mine endpoints/strings out of a mobile app package.

Nothing here couples Glyph to any sibling project (ADR-3): endpoint
reachability is recorded as a neutral catalog attribute, nothing more.
"""
from __future__ import annotations

__version__ = "0.1.0"

from glyph.catalog import Catalog

__all__ = ["Catalog", "__version__"]
