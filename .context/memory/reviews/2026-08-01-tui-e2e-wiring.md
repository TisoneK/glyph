# Session Review — 2026-08-01: TUI E2E wiring (CLI → live capture → Textual dashboard)

## Executive Summary

Target (from `tasks/current.md`): *"The TUI is still not wired E2E. First
synchronize the vendored context core to 0.5.0, then trace and fix the TUI's
end-to-end path from CLI through live capture and Textual dashboard."*

Core sync was already complete (verify passed at 0.5.0, status showed "up to
date" — the 0.5.0 update + kickoff regen had landed in the two prior commits).
The E2E trace found four real wiring gaps between `glyph run live` and the
Textual dashboard; all four are fixed, tested, committed (`54ddb3e`), and
pushed. **156 tests pass, 8 skipped** (was 153 pass / 4 fail / 4 skip — the 4
failures were playwright-dependent browse tests that this session's skip-guard
converted to skips on machines without the `live` extra).

## Discovery Phase

Traced the full path end-to-end:

```
glyph run live <url> (TTY)
  → cli/run.run_live
    → _open_live_dashboard(args)              # TUI takeover
      → run_dashboard(db, live={url, kwargs})
        → GlyphApp(home=False) → DashboardScreen
          → on_mount: action_reload + run_worker(_capture_worker)
            → _capture_worker: Catalog + set_target/clear_target (ADR-12)
              → capture_url(cat, url, **kwargs)   # writes flows, sets meta
          → 1s _tick: _refresh_live + poll capture_status
          → status done → _finalize worker
            → _analyze_once: infer_all + build_dictionary + run_scan
            → run_hunt (SNI, ONCE) + stop timers + full reload
```

Also traced the HomeScreen path (`glyph` bare → URL box → DashboardScreen with
a hand-built live dict) and the headless fallback (`--no-tui`/pipe).

## Baseline Health

- `context-sync verify` → **core OK (0.5.0)**; `status` → up to date.
- Full suite before changes: **153 passed, 4 failed, 4 skipped**. The 4
  failures were all in `tests/test_capture_live.py` browse-mode tests calling
  `_patch_playwright()`, which does `import playwright.sync_api` — playwright is
  NOT in this Mac's `.venv` (only textual+rich are), so the import raised
  `ModuleNotFoundError` instead of skipping. The file's own `_PLAYWRIGHT`
  skip pattern existed but was applied only to `test_graceful_without_playwright`.
- Textual IS installed, so the TUI tests run here.

## Findings (by severity)

### High — TUI silently ignored the CLI stage opt-out flags
- **Description:** `_open_live_dashboard` passed only `{url, kwargs}` to the
  dashboard. `DashboardScreen._analyze_once` always ran `run_scan` and
  `_finalize` always ran `run_hunt(cat)` with default `net=True` — so
  `glyph run live --no-sensitive` / `--no-snihunt` / `--snihunt-no-net` were
  **silently ignored whenever the TUI took over** (i.e. exactly when the user
  asked to skip a stage, it ran anyway — including network recon).
- **Impact:** `--no-snihunt` on a TTY still made outbound DNS/CT/reverse-IP
  calls; `--no-sensitive` still scanned. Flagged behavior diverged between the
  headless and TUI paths.
- **Fix:** thread the three flags through the `live` dict; `_analyze_once`
  skips `run_scan` when `no_sensitive`; `_finalize` skips `run_hunt` when
  `no_snihunt` and passes `net=not snihunt_no_net` (matching `_gather`).

### Medium — a failed capture displayed as "✓ captured"
- **Description:** `_capture_worker` catches exceptions and stores
  `capture_error` in meta, but `_tick` only polled `capture_status` — a
  failure (Playwright missing, nav error, crash) flipped the header to
  "✓ captured" exactly like a success.
- **Fix:** `_tick` reads status+error in one connection (`_capture_state()`)
  and shows `✗ failed · mm:ss · <error>` when an error is present. (Batching
  also removed a second catalog connection per 1s tick; the old `_status()`/
  `_error()` helpers became dead code and were deleted.)

### Low — no live progress in the headless/auto capture path
- **Description:** `capture_url`'s auto path emitted no progress lines, and
  headless `run_live`/`capture live` didn't pass `progress=` — a 30s+ capture
  with no TUI looked frozen (standing user preference: long-running commands
  MUST show live progress).
- **Fix:** driver auto path emits `loading …` / `settling …` / `explore round
  i/N …`; headless `run_live` passes `progress=_progress`.

### Low (test infra) — 4 browse tests hard-failed without playwright
- **Description:** browse tests patch the real `playwright.sync_api` module —
  they cannot run without the `live` extra, but they raised instead of
  skipping (contradicting the file's "testable without Playwright" claim).
- **Fix:** `@_BROWSE_SKIP` skipif marker on all four; module docstring updated
  to say the browse tests need the `live` extra. (They still run fully on the
  user's Windows box where playwright is installed.)

## Fixes Applied

1. `glyph/cli/run.py` — `_open_live_dashboard` threads `no_sensitive` /
   `no_snihunt` / `snihunt_no_net` through the live dict; the url-required
   check now runs BEFORE TUI takeover (a TTY `run live` with no url prints the
   clean CLI error instead of opening a dashboard whose worker would fail);
   headless `capture_live` passes `progress=_progress`.
2. `glyph/tui/app.py` — `DashboardScreen` reads the three flags; `_analyze_once`
   skips sensitive when opted out; `_finalize` skips/honors the SNI hunt; new
   `_capture_state()` batches status+error reads; `_tick` surfaces failures as
   `✗ failed · <error>`; dead `_status()`/`_error()` removed; `_capture_state`
   annotated.
3. `glyph/capture/driver.py` — auto-mode progress lines.
4. `tests/test_capture_live.py` — browse tests skip without playwright;
   docstring corrected.
5. `tests/test_tui.py` — three new tests: stage-flag threading
   (`--no-sensitive` → no scan; `--snihunt-no-net` → `net=False`), `--no-snihunt`
   → no hunt while sensitive still runs, and capture-error surfacing. The new
   tests **poll with a deadline** (40 × 0.1s) instead of fixed sleeps, per
   review feedback — the first draft's fixed `pilot.pause()` sleeps would have
   flaked on slow machines.

## Open Items

- The live TUI path was verified with a **faked** capture (no Playwright in
  this Mac venv). The real Playwright-in-a-worker-thread path still needs
  on-device verification on the user's Windows box (`.venv` there has
  playwright) — unchanged from Session 15.
- `HomeScreen._capture` (bare `glyph` home screen) builds its live kwargs by
  hand and does not carry the opt-out flags — by design (no flags exist on the
  home screen; defaults = full pipeline), but noted for when the home screen
  grows options.
- Backlog unchanged: TUI target picker (Session 18 follow-up), DuckDB backend,
  Rosetta Splink depth, Browse-mode real-world verification on Brave, etc.

## Recommended Next Steps

1. **On-device live verification (user's Windows box):** run
   `glyph run live <auth-protected-target> --browse` with Brave attached; watch
   the dashboard stream flows, verify the header flips to `✓ captured` on
   browser close and that `--no-snihunt`/`--no-sensitive` are honored in the
   TUI. This is the one path mock tests cannot prove (Playwright thread
   affinity — see the Session 19 cont. 5 inefficiency note).
2. TUI target picker (`t` key / sidebar → `set_active_target`) so `glyph
   dashboard` on a multi-target catalog isn't a mixed view — backlog item from
   Session 18.
3. Consider a `--tui` flag on `glyph run har` to open the dashboard as a
   post-ingest exploration view (currently `run har` only prints the summary).
