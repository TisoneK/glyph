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

- **Session:** —
- **Task:** none — Session 16 (2026-07-31) shipped the `glyph.snihunt` stage
  (SNI bug-host hunting, ADR-10). See `agents/sessions.md` Session 16,
  `reviews/2026-07-31-sni-bug-host-hunt.md`, and the backlog follow-ups
  (live carrier verification, zero-rating pattern enrichment, third CT source).
- **Status:** idle
