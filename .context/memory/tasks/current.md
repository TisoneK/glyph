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
- **Task:** none — Session 19 cont. 4 (2026-07-31) implemented ADR-14 (Browse
  Mode): `--browse` flag on `glyph run live` / `glyph capture live` with
  CDP-attach to the user's real browser (Brave/Edge/Chrome) primary + Playwright
  launch-fallback; tab-lineage capture scoping (target tab + popups, or
  all-traffic when no url); `glyph browse --launch` helper. ADR-14 marked
  accepted. See `agents/sessions.md` Session 19 cont. 4 + ADR-14 in
  `plans/decisions.md`. **3 backlog items remain** for the user's on-device
  verification: real-world Brave + auth-protected target test; dedicated
  `cookies` table (v2); split-pane TUI; mitmproxy `glyph capture proxy` for
  Firefox/Safari.
- **Status:** idle
