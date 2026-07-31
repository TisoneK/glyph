# Session Review — HITL review workflow (Session 5)

- **Date:** 2026-07-30
- **Agent:** Claude Code / claude-opus-4-8 (local, bao@local macOS)
- **Role:** engineer
- **Core:** 0.3.0

## Executive summary

Built the human-in-the-loop (HITL) review workflow — the missing half of
Rosetta's thesis (*the tool narrows, the human confirms*). Rosetta already
flagged low-confidence rows; there was no way to act on them. Now a human
can confirm, edit, or reject each decoding, decisions are persisted as
ground truth, and a later `glyph rosetta` re-run never overwrites them.

Chosen deliberately because both items tied to the previous exchange —
the 3.13/Pydantic retarget and real-world validation — were **deferred by
the user**. This work stays entirely on 3.9/dataclasses/stdlib and
*enables* the deferred real-world validation (you'll need to review real
low-confidence rows once you capture a real target).

## What was built

- **Catalog:** a `review_state` column (`confirmed`/`edited`/`rejected`/NULL)
  with an **additive migration** for catalogs created by the pre-review
  schema; a `review_entry()` primitive; review-aware `dictionary()`
  (rejected rows hidden by default). `upsert_dictionary` now skips any
  human-reviewed row, so re-running Rosetta can't clobber decisions.
- **`glyph.review` module** (modular, per user preference): `pending`,
  `confirm`, `edit`, `reject`, `auto_confirm(threshold)`, `stats`, and an
  IO-injected `run_interactive` loop.
- **CLI:** `glyph review` (interactive), `--auto-confirm THRESHOLD`,
  `--id N` with `--reject`/`--set MEANING`, and `--stats`.

## Design notes

- A confirmed/edited row becomes ground truth: confidence → 1.0,
  `needs_review` → 0. Rejected → confidence 0.0, hidden from output.
- IO is dependency-injected in the interactive loop so it's unit-testable
  without a terminal — the interactive path is exercised by the same code
  the CLI uses.
- Stayed pure-stdlib. A Label Studio integration (the backlog's original
  "proper review surface") is now optional, not required — the
  terminal + scriptable workflow covers the core need.

## Baseline health

- `pytest`: **45 passed** (was 32; +13 review tests incl. migration-from-
  old-schema and re-run-protection).
- Manually verified all CLI review paths + the old-schema migration.

## Process note (multi-agent)

A concurrent push (`c69fd06`, the user's own docs edit to
RESEARCH-DEEP-DIVE.md) landed on `origin/main` mid-session. Local had
diverged (1/1). Resolved per the Git Workflow rule: confirmed zero file
overlap, `git rebase origin/main` (clean), re-ran tests, pushed. No work
lost on either side.

## Open items / next steps

- **Real-world validation** (deferred) — now unblocked by this workflow.
- **3.13 + Pydantic retarget** (deferred) — unchanged.
- **DuckDB backend, Splink/positional Rosetta depth, live-capture E2E,
  Daraja recipe** — still in `tasks/backlog.md`.
- **Optional:** Label Studio export/import for teams that want a GUI review
  surface — not needed for single-analyst use.
