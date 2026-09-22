# Geo/browser targeting and live-capture lifecycle review

## 1. Executive Summary

Implemented and verified the requested live-capture hardening. Glyph now accepts explicit target/browser spellings, detects strong geo-block signals without treating ordinary WAF/auth 403 responses as geo-blocks, exposes browser executable/profile/proxy settings, and routes geo-block recovery to the home settings surface. Direct dashboard launches no longer hit a Textual root-screen callback underflow. Windows/macOS quit and worker-stop paths remain bounded and user-visible.

## 2. Discovery Phase

- Reviewed the existing CLI parser and shared live-option plumbing.
- Traced `glyph run live`, `glyph capture live`, the TUI live worker, and Playwright auto/browse capture paths.
- Reproduced the direct-dashboard geo dialog failure: `switch_screen(HomeScreen())` called Textual's result-callback pop on a root dashboard and raised `IndexError: pop from empty list`.
- Verified the installed Textual implementation: `push_screen` registers an internal callback entry even when no user callback is supplied, so `pop_screen` is safe for a Home → Dashboard stack.
- Reviewed existing ADR-14 real-browser capture decisions and the multi-target catalog invariants.

## 3. Baseline Health

- Python compilation: passed.
- Focused suites (`test_capture_live.py`, `test_tui.py`, `test_cli.py`): **60 passed, 1 skipped**.
- Full suite: **195 passed, 5 skipped**.
- `git diff --check`: passed.
- Product commit pushed: `091cf0f` (`fix(live): harden browser targeting and geo-block recovery`).

## 4. Findings

### High — fixed: direct-root geo recovery underflow

A dashboard opened directly by `glyph run live` is the root screen and has no result callback stack suitable for `switch_screen`. Textual therefore raised `IndexError` while trying to pop the outgoing dashboard callback.

**Fix:** defer geo navigation until the modal settles; pop only dashboards above an existing Home screen, and push Home above an inert direct dashboard root.

### Medium — fixed: ambiguous browser/target command forms

Argparse's optional `--browser` value could consume the following URL. The parser now normalizes URL-like values and supports `-b/--browser` plus `-t/--target` while preserving the positional form.

### Medium — fixed: unsafe geo-block classification

Ordinary HTTP 403 responses are commonly authentication, WAF, or bot-protection responses. Detection now requires HTTP 451, explicit country/region language, or a strong network-denial signal.

### Medium — fixed: explicit browser configuration could attach to the wrong process

An explicit executable path/profile/proxy now forces the launch path instead of silently attaching to an unrelated CDP browser. UI settings also enable browse mode and carry the selected values into retries.

### Low — fixed: duplicate proxy settings surface

The geo flow returns to the home screen, which already owns proxy/path/profile inputs. The unused duplicate modal and callback were removed to keep one authoritative settings route.

## 5. Fixes Applied

- Added target URL normalization and `-t/--target` aliases.
- Added `-b/--browser`, executable path, profile directory, and proxy plumbing.
- Added conservative geo-block metadata and immediate TUI visibility.
- Added deterministic geo modal recovery for both direct-dashboard and Home → Dashboard stacks.
- Added Windows-safe top-level interrupt handling and coordinated TUI worker stop behavior through the confirmation flow. An external Ctrl+C arriving outside that flow is suppressed by the wrapper but still needs on-device verification for worker cleanup.
- Added regression coverage for parser forms, geo classification, forced launch, home settings propagation, root navigation, Home → Dashboard navigation, and quit lifecycle.
- Updated README usage documentation.

## 6. Open Items

- Real Windows verification of CDP attach, browser closure, custom executable/profile paths, TUI notifications, and external Ctrl+C worker cleanup remains an on-device follow-up; the local macOS suite cannot exercise the external Windows browser/process boundary.
- A pathological browser/network worker is bounded by the existing shutdown timeout; independently surfacing SNI failure versus core-analysis failure remains a future refinement.

## 7. Recommended Next Steps

1. Run a disposable Brave/Chrome CDP smoke test on Windows with `-b brave -t <host>` and an explicit `--browser-path` plus `--user-data-dir`.
2. Verify closing the owned launch-fallback browser changes the TUI subtitle to `live capture stopped · browser closed`.
3. Keep the existing backlog item for real Windows live-TUI verification until that on-device check is complete.
