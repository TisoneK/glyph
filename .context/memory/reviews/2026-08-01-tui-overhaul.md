# Session 27 — TUI overhaul: redesigned home + stage selection + compact dashboard

- **Date:** 2026-08-01 — Buffy / deepseek-v4-flash
- **User report:** (1) TUI main page: content squeezed top-left, poorly designed
  except the logo; no way to pick which analysis runs (want checkboxes, all ON
  except vpndec); VPN Dec had no input form. (2) Output page: host row becomes
  too big when one/few hosts are long; logo should be inherited but compact so
  the tables get room.

## Root cause found: the home screen's CSS never applied

The "squeezed top-left" layout was a **pre-existing bug invisible to the test
suite**. Textual 8.2.8 only loads a `Screen` subclass's `CSS` when the screen is
**pushed or switched** (`App._load_screen_css` is called from
`push_screen`/`switch_mode`, never from the default-screen mount path in
`_install_screen_stack` — verified in `textual/app.py`). The home screen is the
**default screen**, so its `CSS` (the old `#box { width: 66 }` rule) silently
never loaded → the shell rendered full-width/top-left, and no test asserted CSS
computed values so nothing caught it.

**Fix:** all screen CSS moved into `GlyphApp.CSS` (App CSS loads unconditionally
at startup) with **type-scoped selectors** (`HomeScreen #shell`,
`DashboardScreen #brand`, `FlowDetail #detail`, …) so rules can't leak between
screens. Verified headlessly: `#shell` region `x=9 y=3 w=82` on a 100×40
terminal (was full-width before). Side-fix: `FlowDetail #detail` padding was
scoped to the wrong screen (DashboardScreen) and never matched — now correctly
scoped.

## Changes

1. **`glyph/pipeline.py`** — `run_analysis` gains `no_schema`/`no_rosetta` so
   every stage of the schema→rosetta lane can be skipped independently (the TUI
   checkboxes). A skipped stage leaves its result key `None`; the lane is
   dropped only when BOTH are skipped; early-returns cleanly when every stage is
   opted out (no `ThreadPoolExecutor(max_workers=0)` crash).
2. **`glyph/tui/logo.py`** — new `logo_compact()`: one-line `◈ GLYPH` gradient
   wordmark for the dashboard brand row.
3. **`glyph/tui/data.py`** — new `clip(text, limit)` ellipsis helper; long
   host/URL/SNI cells truncated (flows URL 72, rosetta PATH 48, sensitive HOST
   36, snihunt SNI HOST 44, vpndec HOST 36/SNI 30/FILE 32, with the `—` dash
   fallback preserved).
4. **`glyph/tui/app.py`** —
   - **HomeScreen redesign:** centered `#shell` (width 82), an ANALYSIS STAGES
     panel with checkboxes (schema, rosetta, sensitive, snihunt — all ON by
     default; vpndec OFF) and a VPN config **file input revealed on tick**
     (disabled until then). `_capture` threads `stages` + `vpndec_file` through
     the `live` dict; a ticked-but-empty vpndec path bells instead of silently
     no-oping. (Textual 8.2.8 `Checkbox` uses `value=`/`.value`, NOT `checked` —
     verified.)
   - **DashboardScreen:** compact brand row (`◈ GLYPH · <clipped host>`), stage
     flags from `live["stages"]` with fallback to the CLI opt-out flags,
     `_capture_state()` now returns a dict incl. vpndec status/error, the header
     shows `vpndec ✓/✗` once decode runs, and `_decode_vpndec()` (decode_file +
     add_vpn_config, meta status/error) runs at finalize.
5. **Tests** — pipeline stage-skip; TUI checkbox defaults (incl. a **CSS
   regression guard**: `#shell` region width == 82 at 100-col size — the
   assertion that would have caught the original bug), stage threading, brand
   row, `clip()` + long-host table clipping.

## Validation

- `pytest tests/` → **177 passed / 5 skipped**.
- Headless render probe (Textual `run_test`): home screen centered
  (`#shell` x=9 w=82 on 100×40), all checkboxes on except vpndec, vpnfile
  disabled, buttons render; dashboard brand row `◈ GLYPH` + summary + flows
  table all present.
- 7 reviewer passes (code-reviewer-deepseek-flash), catching: empty-lane pool
  crash, dead `Middle` import, vpndec `—` dash regression, duplicate
  `stages-row` id, `Static.renderable` vs `.render()`, the run_test default-size
  trap (80×24 caps `max-width: 94%` to ~75 → the guard needs 100-col size), and
  the vpndec-empty silent no-op.

## Open items

- Windows-box live-TUI verification (carried over).
- Optional: a `--no-schema`/`--no-rosetta` CLI flag on `run` (the pipeline
  supports it; the CLI doesn't expose it — renderers would need None-guards).
- `glyph dashboard` now gets its CSS too (it was also a default screen) — worth
  an on-device look.
