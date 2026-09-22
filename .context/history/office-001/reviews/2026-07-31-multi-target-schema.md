# Session 18 Review — Multi-Target Catalog Schema (ADR-12)

> **Session:** 2026-07-31 — Super Z / unknown (cloud sandbox, Python 3.12.13)
> **Task:** Replace the single-target catalog (`meta.target_host` + per-run
> `Catalog.reset()` wipe) with a multi-target model: a `targets` table +
> `target_id` on every data row, so multiple targets coexist and a re-run
> only clears THAT target's rows. Surface it via `glyph target list|show|rm`.
> **Outcome:** done. 146 tests pass (was 144; +2 new multi-target tests,
> 1 rewritten). Schema bumped 3 → 4 with an additive, idempotent migration.

---

## 1. What shipped

### Schema (`glyph/catalog/store.py`)
- **New `targets` table** — `id INTEGER PRIMARY KEY` (no AUTOINCREMENT, so
  the reserved id=0 sentinel is insertable), `host TEXT NOT NULL UNIQUE`,
  `label`, `notes`, `created_at`.
- **`target_id` column on every data table** — flows, endpoints, fields,
  dictionary, page_observations, findings, vpn_configs. Every UNIQUE now
  includes `target_id` (endpoints, fields, dictionary, findings, vpn_configs).
- **Reserved "(unassigned)" target (id=0).** Every write stamps a NON-NULL
  `target_id` (explicit > active > unassigned=0). This is REQUIRED because
  SQLite treats `NULL != NULL` in UNIQUE constraints — nullable `target_id`
  would break upsert dedup (two flows with NULL target_id + the same
  endpoint shape would NOT collapse, doubling endpoints and breaking the
  sensitive scan's sequential-ID detector). The unassigned bucket catches
  rows written without `set_target` (legacy tests, REPL scratch) and still
  dedups correctly.
- **`SCHEMA_VERSION` 3 → 4.** Indexes split out of `_SCHEMA` into `_INDEXES`
  so the `target_id` indexes don't fire before migration adds the column
  (this was the `test_migration_adds_review_state` failure — the old probe
  checked only `endpoints` as the v4 canary, but a test seeded an old
  `dictionary` alongside a fresh `endpoints`; fixed by probing EACH table).

### Catalog API
- **`set_target(host, label=None, notes=None) -> int`** — upserts into
  `targets` + activates. Idempotent (re-activating an existing host does
  NOT clear its rows — call `clear_target` for that).
- **`target() -> Optional[str]`** — active target's host, else the latest
  REAL target's host (skips unassigned so the TUI sub_title doesn't read
  "(unassigned)"), else None.
- **`target_id() / set_active_target(id) / clear_active_target()`** —
  instance-state management without creating a target.
- **`targets() / get_target(id) / resolve_target(host_or_id)`** — registry
  reads. `targets()` includes a per-target flow-count subquery.
- **`remove_target(id) -> bool`** — deletes a target AND every row that
  belongs to it (iterates `_DATA_TABLES`).
- **`clear_target(target_id=None) -> Optional[int]`** — the per-run
  idempotent reset. Wipes only the active (or specified) target's rows;
  keeps the target row in `targets`; keeps every other target's data.
  Returns the id cleared, or None if no target was active.
- **`reset()`** — retained for tests + a future `--reset` flag. Full wipe
  (every data table + targets + meta except version).
- **Writes** (`add_flow`, `upsert_endpoint`, `upsert_field`,
  `upsert_dictionary`, `add_page`, `add_finding`, `add_vpn_config`) —
  optional `target_id` param; stamp via `_wtid()` (explicit > active > 0).
- **Reads** (`endpoints`, `all_flows`, `fields_for_endpoint`,
  `enum_candidates`, `dictionary`, `pages`, `findings`, `vpn_configs`) —
  optional `target_id` + `all_targets` params. Default: filter to active
  if set, else all. `_target_filter()` builds the WHERE clause.
- **`summary(target_id=None, all_targets=False)`** — per-target or
  catalog-wide counts. Adds a `targets` count.

### Caller updates (the 4 `reset()` sites + har.py)
- **`glyph/cli/run.py`** — `run_har` passes `clear=True` to `ingest_har`
  (idempotent re-run per target); `run_live` does `set_target(host) +
  clear_target()` before `capture_live`.
- **`glyph/cli/snihunt.py`** — direct-target mode: `set_target(t) +
  clear_target()` (was `reset() + set_target(t)`).
- **`glyph/tui/app.py`** — `_capture_worker`: `set_target(host) +
  clear_target()` (was `reset()`).
- **`glyph/capture/har.py`** — `ingest_har` gained a `clear=False` kwarg.
  Two-pass: pass 1 parses entries + infers the target host; activates +
  (if `clear`) wipes the target's old rows; pass 2 writes. `capture har`
  stays `clear=False` (accumulate); `run har` uses `clear=True` (fresh).
- **`glyph capture live`** unchanged — `capture_url` calls `set_target`
  (idempotent, no clear), so `capture live` keeps ACCUMULATE semantics.

### New CLI: `glyph target`
- `glyph target list [--db X]` — every target + its flow count (rich table
  or plain). Shows the "(unassigned)" bucket too (label="unassigned").
- `glyph target show <host|id> [--db X]` — per-target row counts
  (endpoints/flows/fields/findings/dictionary/pages/vpn_configs).
- `glyph target rm <host|id> [--yes] [--db X]` — deletes a target AND its
  data. Prompts for the host to confirm unless `--yes`.
- `--db` accepted on the parent AND each subcommand (both
  `glyph --db X target list` and `glyph target list --db X` work).

### Tests
- `test_run_resets_catalog_between_targets` → **rewritten** as
  `test_run_coexists_across_targets` (the old "run wipes between targets"
  assertion is wrong by design under ADR-12; the new test asserts both
  targets coexist AND a re-run of one replaces only its rows).
- `test_multi_target_coexists_and_clears_per_target` (new) — two targets,
  clear_target isolation, per-target findings/pages, remove_target.
- `test_unassigned_target_dedupes_upserts` (new) — the NULL-dedup
  regression guard (two flows with no target collapse to one endpoint).
- All 146 tests pass (was 144; +2 new, 1 rewritten, 7 skipped unchanged).

### Migration (v3 → v4)
- `_migrate_to_v4` rebuilds each data table that lacks `target_id`
  (create-copy-drop-rename; SQLite can't ALTER a UNIQUE). Per-table probe
  (a mixed old/new DB rebuilds only the old tables).
- Legacy NULL `target_id` rows → unassigned bucket (id=0).
- Legacy `meta.target_host` → a real `targets` row (label="migrated").
- The unassigned target (id=0) is ensured by `__init__` after migration.
- Verified with a hand-built v3 catalog (script: `scripts/migration_test.py`):
  rows survive, target_id stamped, old host ported, new writes after
  migration stamp correctly.

## 2. Design decisions worth flagging

- **Per-target endpoints (not shared).** The old `endpoints` UNIQUE was
  `(method, host, path_template)` — a normalized URL shape shared across
  captures. ADR-12 makes it `(target_id, method, host, path_template)` —
  two targets hitting the same shape get two endpoint rows. Slightly less
  normalized, but matches "every row has target_id" and makes per-target
  cleanup a single `DELETE WHERE target_id=?`. Fields/dictionary link to
  endpoint_id, so they're implicitly per-target now too.
- **`(unassigned)` is a real target, not NULL.** The NULL-in-UNIQUE
  quirk forced this. The alternative (auto-create a target from the
  flow's host on every write) was rejected as too magical and would
  change `add_flow` semantics. The unassigned bucket is honest: it's
  where scratch rows land, it's visible in `glyph target list`, and it
  can be cleared with `glyph target rm 0`.
- **`capture` accumulates, `run` clears.** This split was already
  implicit (old `capture` didn't `reset()`, old `run` did). ADR-12 makes
  it explicit and per-target: `run` activates + clears one target;
  `capture` just adds traffic to the active (or unassigned) target.
- **TUI shows all targets mixed (MVP).** The dashboard's reads default to
  "active if set else all," and the TUI doesn't set an active target on
  open — so it shows every target's rows. A target picker is a natural
  follow-up (backlog). `glyph target show <host>` gives per-target counts
  in the meantime.

## 3. Verification

- `python -m pytest tests/ -q` → 146 passed, 7 skipped (1.4s).
- `scripts/multi_target_smoke.py` — two targets coexist, clear_target
  isolation, remove_target, per-target findings/pages.
- `scripts/migration_test.py` — v3 catalog with real rows → open with v4
  code → rows survive, target_id=0 stamped, old host ported.
- `glyph target list/show/rm` end-to-end on a synthetic two-target
  catalog (run har alpha + run har beta → list shows both → rm beta →
  list shows only alpha + unassigned).

## 4. Open items / follow-ups (→ backlog)

- TUI target picker (set the active target from the dashboard, filter
  all tabs to it).
- `glyph --target <host>` global flag to scope `glyph sensitive`/`dict`/
  `flows`/`catalog` to one target without passing `--target` per command.
- `glyph target rm 0` is allowed but the unassigned target is re-created
  on next open (by `__init__`); document or guard if it confuses users.
- The `endpoints` table's `reachability` is now per-target-row (good), but
  `set_reachability(endpoint_id, ...)` doesn't take a target filter —
  minor, works because endpoint_id is already per-target.
