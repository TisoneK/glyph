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

- **Session:** 2026-07-31 — Claude Code / claude-opus-4-8 (Session 12)
- **Task:** Implement ADR-5 — split `glyph/cli.py` (517 lines) into a `glyph/cli/`
  package (one module per subcommand + `_output.py`/`_format.py` shared helpers),
  fix the dict/run empty-state messaging inconsistency, and give `glyph sensitive`
  table output (masked values, location, severity, filters, --json). Presentation
  only — stage modules stay the single source of truth.
- **Status:** in-progress
