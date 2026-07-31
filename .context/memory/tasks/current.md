# Current Task (overwrite each session)

Holds exactly one task — the one being worked on right now. Set it at
session start (protocol Step 3), clear it at session end (Step 15). If
you find a stale in-progress entry here, a prior session died mid-task —
check its session entry and backlog before starting.

<!-- TEMPLATE — replace everything below this comment:
- **Session:** YYYY-MM-DD — <agent> / <model>
- **Task:** <what is being worked on right now>
- **Status:** in-progress | done | blocked (<blocker>)
-->

- **Session:** 2026-07-31 — Super Z / unknown (cloud sandbox, Python 3.12.13)
- **Task:** Implement the SNI bug-host hunting feature — a new `glyph.snihunt`
  stage that finds NEW SNI bug-host candidates (reverse-IP lookup, certificate-
  transparency subdomain enumeration, Cloudflare/CDN frontable-edge detection,
  zero-rating heuristics, optional active SNI probe). NOT scraping existing
  bughost.txt lists — only the *process* of discovering new hosts. Auto-runs
  after `sensitive` in `glyph run live`/`run har` (`--no-snihunt` to skip).
  New `glyph snihunt` CLI command + new TUI tab (key 6, "SNI Hunt"). See
  ADR-10 (proposed this session) for the bounded active-recon scope decision.
- **Status:** in-progress
