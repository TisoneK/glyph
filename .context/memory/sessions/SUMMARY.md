# Session Summary (compressed continuity — prunable)

One line per session, newest at the bottom. Durable facts live in their
domain files (`agents/sessions.md`, `plans/decisions.md`,
`inefficiencies/log.md`, …) — this file is only for quick orientation.
If this file exceeds ~40 lines, prune entries older than the last 10.

- 2026-08-01 — Buffy / deepseek-v4-flash — Session 20: fixed the TUI's E2E wiring (stage opt-out flags now honored by the live dashboard; failed captures show ✗ failed; auto-capture progress lines; url check before TUI takeover). 156 pass / 8 skip. Report: reviews/2026-08-01-tui-e2e-wiring.md.
- 2026-08-01 — Buffy / deepseek-v4-flash — Session 21: fixed `pip install -e '.[dev]'` on the Mac — mitmproxy floor lowered to >=9 (mitmproxy 10+ needs Python >=3.10; Mac runs 3.9). Install verified, 159 pass / 5 skip. Also clarified identity: user is Tisone Kironget, "bao" is just the macOS account name.
- 2026-08-01 — Buffy / deepseek-v4-flash — Session 22: installed Playwright Chromium on the Mac + smoke-tested `glyph capture live https://example.com` end-to-end (46 flows, exit 0). Smoke test surfaced a by-type display bug (each type listed twice) — fixed with a shared by_type() aggregator used by report_live + run's _types_line. 161 pass / 5 skip. Report: reviews/2026-08-01-live-capture-smoke.md.
- 2026-08-01 — Buffy / deepseek-v4-flash — Session 23: verified the live Textual dashboard ON-DEVICE on the Mac (`glyph run live https://example.com` in a pty harness): ● LIVE → FLOWS streaming 0→46 → ✓ captured at ~15s, clean quit, catalog persisted. Closes the live-TUI verification open item from Session 15. No code changed. Report: reviews/2026-08-01-live-tui-on-device.md.
