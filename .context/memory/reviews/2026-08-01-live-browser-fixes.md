# Session 32 — Live-browser capture fixes

## Target
Fix five live-browser reports:

1. Chromium displayed the `--no-sandbox` warning.
2. User browsing produced no captured live data.
3. Closing the browser did not notify the app that capture stopped.
4. Launch fallback reopened the previous target/profile page.
5. Users needed a way to select their browser executable/profile.

## Changes

- `glyph/capture/driver.py`
  - Enables Chromium's sandbox on macOS, Windows, and non-root Linux; root Linux retains the unavoidable compatibility fallback and emits a visible warning.
  - Adds an explicit sync Playwright event pump during the browse wait, including a context API call after the last tab closes, so request/response and close/disconnect events continue to dispatch.
  - Records `capture_stop_reason` (`browser_closed`, `user_stopped`, or `interrupted`) in catalog metadata and the returned result.
  - Hooks browser/context close signals and cleanly distinguishes user stop from external browser closure.
  - Clears stale pages in Glyph-owned launch-fallback profiles before opening the requested URL; CDP-attached user tabs are never closed.
  - Gives `--browser-path` precedence over the friendly browser name and supports explicit custom executables.
  - Clears the active target for all-tabs capture so new flows are written to the reserved unassigned bucket instead of the previously selected target.
- `glyph/cli/_shared.py`, `glyph/cli/capture.py`, `glyph/cli/run.py`
  - Centralizes browse-mode detection for `--browser`, `--browse`, explicit path/profile flags, and environment configuration.
  - Supports `GLYPH_BROWSER_PATH` and `GLYPH_BROWSER_PROFILE`.
  - Reports browser-close/user-stop status in CLI output and preserves all-tabs pipeline anchoring.
- `glyph/tui/app.py`
  - Reads stop reason metadata and displays `live capture stopped · browser closed` (or the corresponding user stop) in the dashboard.
  - Passes browser profile/path environment configuration from the home screen.
- `README.md`
  - Documents manual CDP launch, executable/profile flags, environment variables, stale-page behavior, all-tabs behavior, and the root-Linux sandbox limitation.
- `tests/test_capture_live.py`
  - Covers stop reasons, stale launch behavior, sandbox option wiring, parser forms, explicit browser path/profile options, and environment configuration.

## Validation

- Focused: 41 passed, 1 skipped.
- Full suite: 189 passed, 5 skipped.
- `compileall` passed.
- `git diff --check` passed.

## Known boundary / follow-up

- A CDP-attached browser was launched by the user, so Glyph cannot remove flags already present on that external process; the sandbox warning may still appear if the user launched that browser with `--no-sandbox`. Glyph documents this distinction.
- All-tabs capture uses target id 0 (unassigned) for new rows. The live capture surface keeps those rows visible; strict historical-session isolation would require a future capture-session dimension rather than overloading the multi-target host model.
- Real on-device Windows verification of browser close, CDP attach, executable paths, and terminal rendering remains recommended.
