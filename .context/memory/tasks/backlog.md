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
- [x] **Phase-0 proof** (added 2026-07-29 by Claude Code; done 2026-07-30 by Super Z / glm-5.2,
      Session 6) — ran stages 1–4 live against linebet.com/en/line/basketball (headless chromium
      via `glyph.capture.driver`). Rosetta auto-derived a 104-entry dictionary, 99 high-confidence;
      spot-checks match hand-analysis (`templateType=14`→Facebook, `13`→Instagram, `9`→Telegram,
      `17`→X, `3`→Security department, `6`→Queries and suggestions). Locked in as a repeatable
      integration test (`tests/test_real_world.py`, 12 tests) against a real captured fixture
      (`tests/fixtures/real/linebet_contacts.json`). See Session 6 report.
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
- [x] **Live-capture end-to-end run** (added 2026-07-30 by Claude Code; done 2026-07-30 by
      Super Z / glm-5.2, Session 6) — `playwright install chromium` succeeded in the Z.ai
      sandbox; `glyph.capture.driver.capture_url` ran live against linebet.com, captured
      20 flows / 17 endpoints with response bodies + DOM labels, and the full pipeline
      (catalog → schema → Rosetta) decoded 104 entries end-to-end. Reusable script at
      `scripts/live_capture_run.py`. Caveat: the headless browser hit a partial block/
      consent interstitial (`/en/block` referer), so the capture is shallow (20 flows, 7
      labels) — the full betting-line depth needs a non-blocked session or interaction
      (scroll, click-to-expand markets) to trigger the events/odds API calls. See Session 6.
- [ ] **Daraja callback verification recipe** (added 2026-07-30 by Claude Code) — concrete
      early deliverable (RESEARCH-DEEP-DIVE §3g): M-Pesa Daraja doesn't sign callbacks; ship
      a Glyph recipe that documents/verifies the gap. Low-Medium, Kenya-priority.
- [x] **Real-world validation of the pipeline (not synthetic)** (added 2026-07-30 by Claude
      Code; done 2026-07-30 by Super Z / glm-5.2, Session 6) — validated against a REAL live
      capture of linebet.com (not a hand-authored HAR). Rosetta reproduced hand-analysis:
      `templateType` ints → brand/department labels (Facebook, Instagram, Telegram, X,
      Security department, Queries and suggestions, Customer Support), all spot-checks
      correct, 99 of 104 entries high-confidence. Locked in as `tests/test_real_world.py`
      (12 integration tests, kept separate from the unit suite per the backlog item's ask)
      against `tests/fixtures/real/linebet_contacts.json` (real payload, contact values
      redacted, code→label structure preserved). Caveat: the capture was shallow (partial
      block interstitial) and the sibling strategy carried it — the DOM-attribute strategy
      (Rosetta's thesis centerpiece) was exercised but contributed little because the SPA
      hadn't fully rendered when the DOM snapshot was taken. Deeper capture + DOM-strategy
      validation is a follow-up. See Session 6 report.
- [ ] **Retarget to Python 3.13 + evaluate Pydantic models** (added 2026-07-30 by Claude
      Code) — user prefers 3.13 (Windows-stable) + Pydantic. Package was built 3.9/dataclasses
      as a stopgap. Decide with the user, then: bump `requires-python`, drop the `__future__`
      workarounds, and consider replacing `glyph.catalog.models` dataclasses with Pydantic
      (revisits ADR-2's zero-dependency base — Pydantic is a hard dep). Medium.
- [ ] **Optional: Label Studio review surface for teams** (added 2026-07-30 by Claude Code) —
      the terminal + scriptable `glyph review` workflow (Session 5) covers single-analyst use.
      A Label Studio export/import (RESEARCH-DEEP-DIVE §4.6) would give teams a GUI review
      surface. Not needed for solo use; only if a multi-analyst workflow is wanted. Low.
- [ ] **mitmproxy vs Playwright live head-to-head** (added 2026-07-31 by Claude Code) —
      compare endpoint/flow coverage of the mitmproxy addon vs the Playwright driver on the
      same target. BLOCKED locally: the sandbox classifier denies running `mitmdump` as a
      local proxy that upstreams to an authenticated external tunnel. Needs the user to allow
      `mitmdump` (Bash permission rule) or run it themselves and hand over the catalog.
      Grounded prediction (Session 9): Playwright wins for web/DOM targets (captures all
      resource types + the DOM Rosetta needs); mitmproxy's edge is mobile/native no-DOM
      clients — complementary, not competing. Low-Medium.
- [ ] **Verify WebSocket frame capture in the driver** (added 2026-07-31 by Claude Code) —
      `glyph.capture.driver` registers `framesent`/`framereceived` handlers (Session 7), but
      confirm it actually stores frame *payloads* (not just the handshake) end-to-end against
      a live WS target (e.g. live-odds streams). This is the one area mitmproxy would clearly
      capture more if the driver doesn't. Medium.
