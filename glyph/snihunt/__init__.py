"""SNI bug-host hunting — discover NEW bug-host candidates (ADR-10).

The ONE bounded active-recon stage. Discovers candidate SNI hostnames from
the captured surface via reverse-IP lookup, certificate-transparency subdomain
enumeration, Cloudflare/CDN frontable-edge detection, zero-rating heuristics,
and an optional active SNI probe. Does NOT scrape published bughost.txt lists
— the *process* of finding new hosts, not a lookup of known ones.

    from glyph.snihunt import run_hunt, summarize
    run_hunt(catalog)             # writes sni_bug_host findings to the catalog
    summarize(catalog)            # counts by category / severity

Authorization stays with the user (RESEARCH.md §10); Glyph surfaces candidates
only and names no tunneling tool (ADR-3).
"""
from __future__ import annotations

from glyph.snihunt.hunt import parse_evidence, run_hunt, summarize

__all__ = ["run_hunt", "summarize", "parse_evidence"]
