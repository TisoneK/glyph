# Session 22 — Live capture smoke test on the Mac (by-type display bug found + fixed)

Date: 2026-08-01 · Agent: Buffy (deepseek/deepseek-v4-flash) · Core: 0.5.0 · Platform: bao@local macOS

## 1. Executive Summary

Closed the Session 21 open item — `playwright install chromium` (the browser binary)
is now installed in the Mac's `.venv`, and `glyph capture live https://example.com`
was smoke-tested end-to-end against a scratch catalog: it captures flows + DOM labels
and exits 0. The smoke test surfaced one real display bug (the "by type" summary line
listed every resource type twice), which was fixed with a shared `by_type()` aggregator
+ two regression tests. Suite: **161 pass / 5 skip** (was 159/5).

## 2. Discovery Phase

- `.venv/bin/playwright install chromium` — succeeded (browser binary + deps).
- Smoke test: `glyph capture live https://example.com --db /tmp/glyph-smoke.db` →
  captured 40 flows + 106 DOM labels from the example.com → iana.org redirect chain,
  exit 0, catalog populated (endpoints + 1 page observation). Re-ran after the fix:
  46 flows + 46 DOM labels, exit 0.
- Display bug observed in the report: `by type:` listed each type TWICE
  (`document=6` twice, `font=3` twice, …).

## 3. Baseline Health

159 pass / 5 skip before the change (Session 21). All tests green throughout; no
flaky-timeout or environment issues on this run.

## 4. Findings

### Medium — "by type" summary line double-counts every resource type (found live)

The driver tags response-side flows `playwright:<type>` and request-side flows
`playwright:request:<type>` (see `glyph/capture/driver.py` `_make_recorders`).
Two display sites handled the split incorrectly:

- `glyph/cli/_shared.py::report_live` printed each `by_source` key verbatim → every
  type appeared twice (once per side).
- `glyph/cli/run.py::_types_line` used a dict comprehension `{k.split(":")[-1]: v}` →
  same key twice = last-wins, silently **dropping** one side's count (undercount).

Both made the capture summary misleading (doubled or undercounted totals).

## 5. Fixes Applied

- **`glyph/cli/_shared.py`** — new `by_type(res) -> dict[str, int]` helper: sums the
  driver's per-source counters into one count per type by taking the last
  `:`-segment (`playwright:document` + `playwright:request:document` → `document`,
  summed). `report_live` now uses it.
- **`glyph/cli/run.py`** — `_types_line` imports `by_type` at module level (added to
  the existing `glyph.cli._shared` import block; function-local import removed) and
  uses it.
- **`tests/test_cli.py`** — two new tests: `by_type` aggregation
  (`document=3` response + `document=3` request → `document=6`) and `report_live`
  printing each type once with summed counts.

Reviewed by code-reviewer-deepseek-flash in parallel with test runs (multiple passes);
nits applied: module-level import placement, `dict[str, int]` annotations.

## 6. Open Items

- Real live-TUI verification on the user's **Windows** box (playwright present there)
  — the one path mock tests can't prove (unchanged from Sessions 20/21).
- TUI target picker for multi-target catalogs (Session 18 backlog) — unchanged.
- Backlog unchanged (DuckDB backend, Daraja recipe, 3.13 retarget, …).

## 7. Recommended Next Steps

- `glyph run live https://example.com` on this Mac (now that chromium is installed)
  to verify the live Textual dashboard streaming path on-device — the TUI's capture
  worker + progress is still untested with a real browser on this box.
- If a real target is available (user's permission), a browse-mode capture
  (`--browse`) to exercise ADR-14 on-device.
