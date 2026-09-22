# Session 31 — Quit confirmation and coordinated SNI analysis

## Request

- Windows: clicking the quit confirmation should actually shut Glyph down.
- macOS: quitting should always show confirmation instead of exiting directly.
- Clarify whether SNI hunting is detached from parallel host processing.

## Implementation

- `QuitConfirmScreen` now starts `GlyphApp.request_shutdown()` directly from the confirmed button path instead of dismissing first and relying on a screen callback. This keeps the modal mounted while shutdown status is rendered and avoids the Windows screen-transition race.
- `GlyphApp` intercepts Textual's native `Ctrl+Q` and `Ctrl+C` actions, routing both through the same confirmation modal. Existing `q`/`Escape` routes remain confirmation-based.
- Shutdown waiting is an async Textual worker, so final `app.exit()` runs on the Textual event loop rather than through a thread callback. Tracked workers still receive the live capture stop event first. A 10-second visible timeout prevents a pathological browser/network worker from making the UI impossible to close; it does not forcibly kill the Python worker.
- Added regression coverage for native shortcuts, confirmed shutdown waiting for a tracked worker, and the real modal status update.
- Added `run_pipeline()`: schema→Rosetta and sensitive remain the core analysis lanes, while the target-pinned SNI lifecycle runs concurrently in its own executor future. CLI headless runs and TUI finalization now use this coordinated wrapper. Individual `run_analysis()` and `run_snihunt()` APIs remain available.
- Added a pipeline overlap regression test. Every lane still opens its own target-pinned Catalog connection; no sqlite connection crosses threads.

## SNI boundary

SNI is no longer sequentially delayed until core analysis completes. Its bounded DNS/CT/reverse-IP/probe work still processes candidates serially inside `run_hunt()` by design, preserving rate limits and avoiding uncontrolled public-network fan-out. Per-host parallelism is therefore intentionally not introduced.

## Validation

- Focused TUI + pipeline: 32 passed.
- Full suite: 188 passed, 5 skipped.
- `compileall` and `git diff --check`: passed.

## Remaining verification

- Verify the native quit shortcuts and real confirmation button in an actual Windows terminal/console.
- Verify real CDP/browser capture stop and shutdown on Windows.
- A shutdown timeout can leave a worker thread alive briefly; this is surfaced explicitly rather than silently claiming a clean worker completion.
