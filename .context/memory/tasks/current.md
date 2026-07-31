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
- **Task:** none — Session 17 (2026-07-31) shipped (1) the Session 16 flaw
  fixes (5 of 8 fixed, 3 backlog) and (2) the `glyph.vpndec` VPN-Config
  Decoder stage (ADR-11). See `agents/sessions.md` Session 17,
  `reviews/2026-07-31-vpn-config-decoder.md`, and the backlog follow-ups
  (port HAT/NPV/NSH/VHD decryptors; port HC v2.7+/EHI v2 ChaCha20 schemes;
  snihunt probe tests + 429 handling).
- **Status:** idle
