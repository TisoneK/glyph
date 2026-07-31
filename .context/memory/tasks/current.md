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
- **Task:** none — Session 15 (2026-07-31) shipped TUI Phase 2 (live) + the home/splash screen.
  VERIFY on the user's Windows box: the Playwright browser live path (sync Playwright in a Textual
  worker + concurrent WAL writers). See `agents/sessions.md` Session 15, ADR-9.
- **Status:** idle
