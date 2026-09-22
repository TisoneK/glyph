# Session 28 — Quit lifecycle, detached SNI, and TUI target switching

## Executive Summary
Implemented the three requested TUI/pipeline improvements: quit confirmation with graceful worker shutdown, an explicitly separate SNI-hunt lifecycle, and switching among previously processed targets from the dashboard.

## Discovery Phase
- `glyph/tui/app.py` owns the Textual home/dashboard lifecycle and live capture workers.
- `glyph/pipeline.py` previously put schema→Rosetta, sensitive, and SNI hunting in one pool.
- `glyph/catalog/store.py` already persisted `active_target_id` and exposed `targets()` / `set_active_target()` for multi-target catalogs.
- Existing live workers use separate SQLite connections with WAL and target pinning.

## Baseline and Validation
- Focused TUI/pipeline/catalog/CLI tests: 48 passed.
- Full suite: **180 passed, 5 skipped**.
- `compileall` and `git diff --check`: passed.
- CLI help smoke check confirms core parallel analysis plus independent bounded SNI reconnaissance.

## Fixes Applied

### Quit confirmation and graceful shutdown
- Added `QuitConfirmScreen` with explicit Quit / Keep working actions and Escape/`n` cancellation.
- Replaced direct `app.exit()` bindings with confirmation on Home and Dashboard.
- Tracked capture, analysis, finalization, and SNI workers in `GlyphApp`.
- Shutdown waits for worker completion instead of pretending Python thread cancellation is forceful; the app chrome shows “finishing active work…” while SQLite/Playwright work drains safely.
- Escape/back follows the same confirmation path when it would otherwise close the app.

### Independent SNI processing
- `run_analysis()` now owns only the core schema→Rosetta and sensitive lanes; its `sni: None` slot remains only for renderer result-shape compatibility.
- Added `run_snihunt()` with its own target-pinned Catalog lifecycle.
- Headless CLI awaits `run_snihunt()` for complete reports.
- Live TUI starts SNI as a separately tracked worker after core finalization, so network reconnaissance is not coupled to the core pool or its result timing.

### Target switching
- Added `TargetPickerScreen` on dashboard key `t`.
- Picker lists real registered targets, excludes the reserved `(unassigned)` bucket, marks the current target, and reloads all dashboard views after selection.
- Switching is blocked while any tracked worker is active, preventing a live capture or analysis from being redirected.
- Worker writes remain explicitly pinned to their original capture target.

## Open Items
- Graceful shutdown intentionally waits for uncancellable Python threads; a future session may add a bounded timeout/fallback policy for pathological browser/network hangs.
- Windows live-TUI verification remains carried from prior sessions.

## Recommended Next Steps
- Verify the new quit and target-picker interactions on the Windows Textual environment.
- Consider a shutdown timeout UX after observing real Playwright/SNI hangs.
