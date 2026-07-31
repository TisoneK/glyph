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

- **Session:** 2026-07-31 — Claude Code / claude-opus-4-8 (Session 13)
- **Task:** Online research + write two scope ADRs the user flagged as missing:
  (A) capture scope — HTTP/HAR level vs raw-packet (.cap/pcap); (B) mobile package
  handling — APK/IPA vs XAPK/APKS/split-APK/OBB. Research first for context, then
  record grounded ADRs.
- **Status:** in-progress
