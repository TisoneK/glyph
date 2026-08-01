# Session 24 — Parallel analysis pipeline (ADR-15) + unassigned-bucket bug fix

Date: 2026-08-01 · Agent: Buffy (deepseek/deepseek-v4-flash) · Core: 0.5.0 · Platform: bao@local macOS

## 1. Executive Summary

The user asked why the post-capture stages (schema, rosetta, sensitive, snihunt) wait
for each other during `run`/`run live`, and set the target: run them in parallel. The
real dependency graph has only ONE edge (schema → rosetta), so the stages now run as
THREE concurrent lanes via a new `glyph/pipeline.py::run_analysis()`: schema→rosetta
(chained), sensitive, snihunt — the slowest stage (network recon) no longer waits
behind the others. The parallelization forced a latent bug into the open: TUI analysis
workers opened a fresh Catalog with no active target, so fields/dictionary/findings
silently landed in the `(unassigned)` bucket. Fixed by per-lane `set_target`.
**165 tests pass / 5 skip** (was 161/5; +4 new pipeline tests).

## 2. Discovery Phase

- Traced the sequential chain: `glyph/cli/run.py::_gather` ran `infer_all` →
  `build_dictionary` → `run_scan` → `run_hunt` strictly in order.
- Read every stage entry point to establish the true dependency graph:
  - `schema→rosetta` MUST chain: rosetta's `dom_attribute` strategy reads
    `catalog.enum_candidates()` — the fields schema inference writes.
  - `sensitive` (`run_scan`) scans flows directly — no dependency on schema/rosetta.
  - `snihunt` (`run_hunt`) reads the captured host surface — independent of all three,
    and the slowest (bounded network recon: DoH, CT logs, reverse-IP).
- Confirmed the catalog already supports concurrent writers (WAL + busy_timeout=5000,
  built for the TUI's capture/analyze overlap in Session 15).
- **Latent bug surfaced by Session 23's own verification:** `glyph target show
  example.com` reported findings 0 / fields 0 / dictionary 0 while the dashboard
  displayed findings — because the TUI's `_analyze_once`/`_finalize` opened a fresh
  `Catalog(self.db_path)` with NO active target, so every analysis write fell into the
  reserved `(unassigned)` bucket (id=0). `D.summary()` reads with no active target →
  falls back to all targets, which masked it in the dashboard.

## 3. Baseline Health

161 pass / 5 skip before this session. All green throughout; no flaky-timeout issues
(the barrier test is deterministic — 3 lanes × blocking entry points, max_workers=3).

## 4. Findings

### High — analysis writes silently landed in the (unassigned) bucket (fixed)

The TUI's live analysis workers opened a fresh Catalog connection without activating
the target. Every `upsert_field` / `upsert_dictionary` / `add_finding` stamped
`target_id = 0` (the reserved unassigned bucket) instead of the capture target.
Session 23's on-device `glyph target show example.com` proved it empirically (findings
0 / fields 0 / dictionary 0 while the dashboard displayed them). This bug also meant
`--target` filters and per-target clear/re-run never saw the live dashboard's analysis.

### Low — stages serialized without a real dependency (the user's observation, fixed)

snihunt waited for schema+rosetta+sensitive even though nothing connects them; sensitive
waited for schema+rosetta even though it scans flows directly. `run har`/`run live` wall
clock was the SUM of all stages instead of the max.

## 5. Fixes Applied

- **`glyph/pipeline.py` (new, ADR-15):** `run_analysis(db_path, *, target, no_sensitive,
  no_snihunt, snihunt_no_net, progress)` runs THREE LANES over a `ThreadPoolExecutor`:
  lane 1 = schema→rosetta (chained), lane 2 = sensitive, lane 3 = snihunt. Opt-out
  flags skip lanes. Result shape `{sch, ros, sens, sni}` — the CLI renderers are
  untouched. Every lane opens its OWN Catalog connection and re-activates the target
  first (`set_target(target)`), fixing the unassigned-bucket bug for BOTH the TUI and
  the headless CLI. Progress callbacks are lock-guarded so concurrent lane lines never
  interleave mid-print. A lane exception propagates after the pool drains (fail-fast
  preserved; other lanes' writes persist and a re-run is idempotent).
- **`glyph/cli/run.py`:** `_gather` now delegates to `run_analysis(cat.path,
  target=cat.target(), ...)`; `{cap, sch, ros, sens, sni}` shape unchanged.
- **`glyph/tui/app.py`:** `_analyze_once` (live ticks) runs schema→rosetta ∥ sensitive
  and skips snihunt (finalize-only per ADR-10); `_finalize` runs all three incl. the
  hunt; new `_target_host()` helper parses the live url's hostname for lane anchoring.
- **Tests:** `tests/test_pipeline.py` (new) — a `threading.Barrier(3)` test that PROVES
  the three lanes overlap in time (if serialized, each lane would block forever and the
  barrier would time out); a target-anchoring regression test (rows on the active
  target, ZERO in the unassigned bucket); flag-skip tests (no_sensitive / no_snihunt /
  snihunt_no_net). `tests/test_tui.py` fakes updated to accept the `progress=` kwarg the
  pipeline now passes to `run_hunt`.
- **ADR-15** appended to `plans/decisions.md` (accepted/implemented).

Reviewed by code-reviewer-deepseek-flash in parallel with test runs (4 passes: design,
first test run caught the `.t`-TLD seed, closing pass on the committed diff + cosmetic
nit — an unidiomatic test lambda replaced with named helpers).

## 6. Open Items

- **Capture-tool parallelism** (the other reading of "parallel from different tools" —
  Playwright ∥ mitmproxy addon writing to one target) remains unbuilt; backlog item
  "mitmproxy vs Playwright live head-to-head" already points at it. Note the user
  clarified this session's ask was the analysis stages; capture-tool parallelism is a
  separate feature.
- Live-TUI verification on the user's Windows box (unchanged, now optional — the
  design is proven on-device on the Mac).
- Backlog unchanged: TUI target picker, DuckDB backend, Daraja recipe, 3.13 retarget.

## 7. Recommended Next Steps

- Optionally: `glyph run live https://example.com` on-device and confirm the dashboard
  now shows findings/fields/dictionary against the target (regression check of the
  unassigned-bucket fix) — Session 23's pty harness can drive it.
- If capture-tool parallelism is wanted, spec Playwright ∥ mitmproxy against one target
  (one command, two writers, WAL already supports it).
