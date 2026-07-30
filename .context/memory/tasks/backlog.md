# Backlog (append-only)

Open items for future sessions. Append at the bottom; never delete or
reorder. When an item is done, check it off and note the session/commit —
don't remove the line.

<!-- TEMPLATE — copy below the last entry:
---
- [ ] **<short title>** (added YYYY-MM-DD by <agent>) — <enough context that
      a fresh agent can act on this without any chat history. Severity if known.>
-->

---
- [x] **Build MVP: pipeline stages 1–4 + drift monitor** (added 2026-07-29 by Claude Code;
      done 2026-07-30 by Claude Code, Session 4) — built as the `glyph-re` package: all 10
      stages (capture, catalog, schema, rosetta, fingerprint, auth, gating, codegen, drift,
      mobile) + CLI, 32 passing tests. See `reviews/2026-07-30-build-base-system.md`.
      Follow-ups tracked as new backlog items below (HITL UI, DuckDB, Splink, live-capture E2E).
- [ ] **Phase-0 proof** (added 2026-07-29 by Claude Code) — run stages 1–4 against any
      target with opaque codes + a visible UI; have Rosetta auto-derive its code dictionary
      and check it reproduces hand-analysis. RESEARCH.md §9. Gate for building the rest.
- [x] **Decide repo/service split + catalog store** (added 2026-07-29 by Claude Code;
      done 2026-07-30 by Claude Code, ADR-2) — resolved: monorepo, stages as packages,
      catalog as a library, SQLite → DuckDB → Postgres. See `plans/decisions.md` ADR-2.
- [x] **README: proposed repo/package layout** (added 2026-07-29 by Claude Code;
      done 2026-07-30 by Claude Code, Session 4) — README now documents install, quickstart,
      and the pipeline/package table matching the built structure.

---
- [x] **HITL review UI for low-confidence dictionary rows** (added 2026-07-30 by Claude Code;
      done 2026-07-30 by Claude Code, Session 5) — built `glyph.review` + `glyph review`
      (interactive + `--auto-confirm` + single-entry `--id/--reject/--set` + `--stats`).
      Decisions persist (review_state column + migration) and survive Rosetta re-runs.
      Label Studio integration is now OPTIONAL, not required — see follow-up below.
      See `reviews/2026-07-30-hitl-review-workflow.md`.
- [ ] **DuckDB catalog backend** (added 2026-07-30 by Claude Code) — the store interface
      (`glyph.catalog.store.Catalog`) is ready for the ADR-2 promotion (SQLite → DuckDB when
      drift analytics matter). Not yet implemented. Medium.
- [ ] **Rosetta depth: Splink + positional/value-inferred correlation** (added 2026-07-30 by
      Claude Code) — current model is a hand-rolled noisy-OR over sibling/DOM/reference
      strategies. Add probabilistic matching (Splink, §4.6) and correlation for codes that
      neither sit next to a label nor appear in the DOM. Medium.
- [ ] **Live-capture end-to-end run** (added 2026-07-30 by Claude Code) — `capture/mitm.py`
      + `capture/driver.py` are written but only import-tested (the `live` extra isn't
      installed). Do a real `playwright install chromium` capture against an authorized
      target and confirm the DOM-label path decodes end-to-end. Medium.
- [ ] **Daraja callback verification recipe** (added 2026-07-30 by Claude Code) — concrete
      early deliverable (RESEARCH-DEEP-DIVE §3g): M-Pesa Daraja doesn't sign callbacks; ship
      a Glyph recipe that documents/verifies the gap. Low-Medium, Kenya-priority.
- [ ] **Real-world validation of the pipeline (not synthetic)** (added 2026-07-30 by Claude
      Code) — per the user's testing preference (`user/preferences.md` → Testing): the 32
      unit tests use hand-authored HARs. Validate against a REAL captured HAR from an
      authorized target (real DOM, real messy codes) and confirm Rosetta reproduces
      hand-analysis. Add these as integration tests kept separate from the unit suite. This
      is the honest "does it work?" gate — do not report unit-test pass rates as real-world
      evidence. High.
- [ ] **Retarget to Python 3.13 + evaluate Pydantic models** (added 2026-07-30 by Claude
      Code) — user prefers 3.13 (Windows-stable) + Pydantic. Package was built 3.9/dataclasses
      as a stopgap. Decide with the user, then: bump `requires-python`, drop the `__future__`
      workarounds, and consider replacing `glyph.catalog.models` dataclasses with Pydantic
      (revisits ADR-2's zero-dependency base — Pydantic is a hard dep). Medium.
- [ ] **Optional: Label Studio review surface for teams** (added 2026-07-30 by Claude Code) —
      the terminal + scriptable `glyph review` workflow (Session 5) covers single-analyst use.
      A Label Studio export/import (RESEARCH-DEEP-DIVE §4.6) would give teams a GUI review
      surface. Not needed for solo use; only if a multi-analyst workflow is wanted. Low.
