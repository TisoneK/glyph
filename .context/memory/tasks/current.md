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
- **Task:** (cleared) Session 22 done — `playwright install chromium` installed on the Mac (browser binary), `glyph capture live https://example.com` smoke-tested end-to-end (46 flows, exit 0); the smoke test exposed a by-type display bug (types listed twice) — fixed with a shared by_type() aggregator + 2 regression tests. 161 pass / 5 skip.
- **Status:** done
