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
- **Task:** (cleared) Session 25 done — ADR-15 wall-clock profile: 1.00x offline (CPU-bound, GIL) / 1.44x controlled-I/O (snihunt network dominates, CPU hidden); no product code changed (throwaway benchmarks in /tmp).
- **Status:** done
