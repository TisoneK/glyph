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

- **Session:** 2026-07-31 — Claude Code / claude-opus-4-8 (Session 10)
- **Task:** Build the `glyph.sensitive` stage — passively flag (a) sensitive
  data (PII/secrets/financial) in captured payloads, (b) sensitive endpoints
  (auth/admin/payment/account), and (c) risk indicators (secrets in query,
  missing auth on sensitive data, wildcard CORS, missing security headers,
  debug endpoints, sequential-ID/IDOR). FLAG-AND-LOCATE, keep values intact
  (user correction: redaction is NOT a default, only an opt-in export). New
  catalog `findings` table + `glyph sensitive` CLI. Passive analysis only —
  no active scanning/exploitation.
- **Status:** done (sensitive stage shipped, 88 tests) — now running a live
  test to exercise `glyph sensitive` against a real target.
