# Session 23 — Live TUI dashboard verified on-device (macOS)

Date: 2026-08-01 · Agent: Buffy (deepseek/deepseek-v4-flash) · Core: 0.5.0 · Platform: bao@local macOS

## 1. Executive Summary

The longest-standing live-path open item — real live-TUI verification (carried since
Session 15) — is **closed**. With Chromium now installed (Session 22), `glyph run live
https://example.com` was driven through a real pty: the Textual dashboard streamed the
capture in real time (`● LIVE` header ticking, FLOWS incrementing on the 1s ticks),
flipped to `✓ captured`, quit cleanly on `q`, and persisted 46 flows + 1 page to the
catalog. No failures, no tracebacks, no code changes needed.

## 2. Discovery Phase

- tmux is **not installed** on this Mac; `script` and `expect` are available.
- Wrote a small Python pty harness (stdlib only) — spawns the command under
  `pty.fork()` with `TERM=xterm-256color` + a 120×30 winsize, records the raw stream
  to `/tmp/glyph-tui.raw`, regex-detects header state transitions and FLOWS counts,
  sends `q` 8s after `✓ captured`, drains until child exit.

## 3. Baseline Health

161 pass / 5 skip (Session 22). No product code touched this session; the suite was
not re-run because nothing changed (verification-only session).

## 4. Findings

No defects. On-device behavior matches the mock-test predictions exactly:

| Check | Result |
|---|---|
| `● LIVE mm:ss` header | seen at t=1.6s, ticking |
| FLOWS streaming | 0 → 2 → 22 → 23 → 46 across the 1s ticks (~13s) |
| `✓ captured · mm:ss` header | at t=14.8s |
| `q` quit | clean at t=22.8s, no orphaned process |
| `✗ failed` / tracebacks | none |
| Catalog persistence | 46 flows, 1 page, target example.com |

The capture-worker + WAL concurrent-writer + guarded 1s/4s tick design works
on-device as designed (Session 15's "implemented but NOT verified" caveat is resolved).

## 5. Fixes Applied

None (no code changes).

## 6. Open Items

- Windows-box live-TUI verification remains the only unverified live path
  (playwright present in `.venv` there) — optional; the design is now proven on-device.
- Backlog unchanged: TUI target picker (Session 18), DuckDB backend, Daraja recipe,
  Python 3.13 retarget.

## 7. Recommended Next Steps

- Optionally repeat this pty-driven verification on the Windows box to close the
  last environment-specific gap.
- If a real authorized target is available, run the same on-device live capture
  against it (richer flows, real findings) to exercise the dashboard with real data.
