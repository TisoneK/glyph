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

- **Session:** 2026-08-01 — Buffy / deepseek-v4-flash
- **Task:** (cleared) Session 20 done — TUI E2E wiring fixed: stage opt-out flags honored by the live dashboard, capture errors surfaced as ✗ failed, auto-mode progress lines, url check before TUI takeover. 156 pass / 8 skip. Report: `.context/memory/reviews/2026-08-01-tui-e2e-wiring.md`.
- **Status:** done
