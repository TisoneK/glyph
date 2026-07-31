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

- **Session:** 2026-07-31 — Super Z / unknown (cloud sandbox)
- **Task:** Implement the VPN-Config Decoder/Sniffer feature (ADR-11) — a new
  `glyph.vpndec` stage that decrypts VPN config files (.hc/.ehi/.dark/.ziv/.tls)
  the user supplies. Borrows algorithms from InjectX (cloned separately at
  /home/z/my-project/injectx-work/InjectX), NOT coupled to it. New `glyph vpndec
  <file>` CLI command, new `vpn_configs` catalog table, new TUI tab (key 7 "VPN
  Dec"). `[crypto]` extra (pycryptodome) with HAS_CRYPTO fallback. File-triggered,
  not auto-run. Prior to this: fixed the 8 flaws from Session 16 (committed
  fff1f18 + 34e3d6a).
- **Status:** in-progress
