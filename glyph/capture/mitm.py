"""mitmproxy addon — live capture into a Glyph catalog (optional backend).

Run it with mitmproxy (install the ``live`` extra first)::

    GLYPH_DB=glyph.db mitmdump -s glyph/capture/mitm.py

Every response mitmproxy sees is written to the catalog as a flow. This
module imports cleanly without mitmproxy installed; it only needs it at
runtime, when mitmproxy itself loads the addon.
"""
from __future__ import annotations

import os
from typing import Any

from glyph.catalog import Catalog, Flow


class GlyphAddon:
    """A mitmproxy addon that appends each flow to a catalog.

    Flows are stamped with the persisted CURRENT target (Session 26) — the
    addon is passive and has no URL of its own, so it inherits the capture
    context. Note: mitmdump sees EVERY host's traffic, so all of it buckets
    under that one target; use a per-target proxy run (or the unassigned
    fallback on a fresh catalog) to keep hosts separate.
    """

    def __init__(self, db_path: str = "glyph.db") -> None:
        # restore_active=True: stamp flows on the persisted current target
        # (Session 26) instead of the (unassigned) bucket when the addon
        # runs standalone — mitm writes what the current target's capture
        # context expects.
        self.catalog = Catalog(db_path, restore_active=True)

    def response(self, flow: Any) -> None:  # mitmproxy http.HTTPFlow
        req, resp = flow.request, flow.response
        try:
            req_body = req.get_text(strict=False)
        except Exception:
            req_body = None
        try:
            resp_body = resp.get_text(strict=False)
        except Exception:
            resp_body = None
        self.catalog.add_flow(Flow(
            method=req.method,
            url=req.pretty_url,
            host="",
            path="",
            req_headers=dict(req.headers),
            req_body=req_body,
            status=resp.status_code,
            resp_headers=dict(resp.headers),
            resp_body=resp_body,
            resp_mime=(resp.headers.get("content-type") or "").split(";")[0] or None,
            source="mitm",
        ))

    def done(self) -> None:
        self.catalog.close()


# mitmproxy discovers a module-level ``addons`` list.
addons = [GlyphAddon(os.environ.get("GLYPH_DB", "glyph.db"))]
