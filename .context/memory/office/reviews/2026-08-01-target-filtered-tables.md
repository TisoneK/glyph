# Session 26 Review — Table displays scoped to the current target (2026-08-01)

> **Session:** 2026-08-01 — Buffy / deepseek-v4-flash
> **Task:** Target (user report): "Tables display. The outputs are not being
> filtered by session or target, it fetches all from db instead of displaying
> only those that are tied to the current target."
> **Outcome:** done. **171 pass / 5 skip** (was 166/5; +5 new tests).

## Root cause

The store layer was already correct: every read filters to the *active*
target (`_target_filter`), and ADR-12 documents "reads filter to the active
target by default (fall back to 'all targets' when no target is active)". The
problem: the active target was **in-memory only** (`Catalog._active_target_id`).
Every CLI/TUI display command opens a FRESH `Catalog` (via `_shared.catalog()`
or `Catalog(self.db_path)`), which starts with NO active target — so reads fell
back to **all targets' rows**. Every table (`glyph flows`, `dom`, `dict`,
`sensitive`, `snihunt`, `schema`, `rosetta`, `catalog`, the dashboard) showed
every target's data mixed together. Only `glyph target show <host>` worked,
because it calls `set_active_target` itself.

## Fix

1. **Persist the active target** — `meta.active_target_id`, written by
   `set_target` / `set_active_target`, cleared by `clear_active_target` /
   `set_active_target(None)` / `remove_target`. Self-cleaning on stale or
   garbage ids. The reserved **(unassigned) bucket (id=0) is never persisted
   or restored as current** — `glyph target show 0` is a one-shot peek that
   must NOT nuke a real persisted current target (renderers already skip id=0
   for the "current" marker).
2. **`Catalog(path, restore_active=True)`** opt-in — display/stage commands
   pass it; **write paths (`run`/`capture`) stay pristine** and set their own
   target per ADR-12, so capture semantics are unchanged.
3. **Opted in:** all display + stage CLI commands (flows, dom, dict, catalog,
   codegen, review, sensitive, snihunt, schema, rosetta, vpndec, fingerprint,
   gating, auth, mobile), every TUI read site (reload / live refresh / tab
   activation / flow detail / sub-title / capture-state poll), `pipeline._open()`
   (a `None` target now falls back to the persisted current target instead of
   the unassigned bucket), and the mitmproxy addon (docstring documents that
   all proxy traffic buckets under the persisted current target).
4. **`glyph target list`** marks the current target (rich / plain / JSON, with
   the same `id != 0` guard everywhere); **`glyph target show <host>`** now
   persists the switch and hints that tables follow it.
5. **Bonus latent bugs this surfaced and fixed:** standalone `glyph sensitive`,
   `glyph snihunt` (catalog mode), `glyph schema`, `glyph rosetta` previously
   wrote their output to the **(unassigned)** bucket (id=0) when a current
   target existed; they now target the current target.

## Tests (+5)

- `tests/test_catalog.py`: `test_active_target_persists_across_opens`,
  `test_clear_and_remove_clear_persisted_active`,
  `test_restore_ignores_unknown_meta_id`,
  `test_restore_never_resurrects_unassigned_bucket` (forged meta "0" is
  cleaned up; `set_active_target(0)` is one-shot and does not wipe a real
  persisted current target).
- `tests/test_cli.py`: `test_display_tables_scope_to_current_target` (after
  two `run har` passes, `glyph flows`/`glyph dict` show only the last target;
  `glyph target show <other>` flips them),
  `test_target_list_marks_current`.

## Review

Reviewer (code-reviewer-deepseek-flash) ran 4 parallel passes. It caught three
real issues, all fixed:
1. `glyph vpndec` was still writing decoded configs to the unassigned bucket —
   now invisible in the (newly filtered) VPN tab → opted into restore_active.
2. `pipeline._open()` still wrote to unassigned when `target=None` → restores
   the current target as fallback.
3. **`set_active_target(0)` destroyed a persisted real target** (it cleared
   the meta unconditionally), so `glyph target show 0` would silently reset
   the current context → now one-shot display only, real target survives.

Also scoped fingerprint/gating/auth/mobile for consistency and added the
id!=0 JSON marker guard. Drift intentionally stays whole-catalog (it diffs two
snapshot files; restoring a target would hide non-current drift).
