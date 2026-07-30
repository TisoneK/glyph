# Session Review — Build the general-purpose Glyph base system

- **Date:** 2026-07-30
- **Agent:** Claude Code / claude-opus-4-8 (local, bao@local macOS)
- **Role:** engineer
- **Core:** 0.3.0

## Executive summary

The project moved from **research to build**. The user directed: *"build
everything, general-purpose tool not for specific target, remove injectx
framing."* This session delivers a working, installable, tested Python
package (`glyph-re`) implementing the full composable-stages pipeline over
a shared catalog (ADR-2), with Glyph made fully standalone (ADR-3). 32
tests pass; the `glyph` console script installs and runs.

## What was built

A pure-stdlib base package (`glyph/`), stages as subpackages:

| Stage | Package | Status |
|-------|---------|--------|
| capture | `glyph.capture` | HAR ingestion + HTML label harvester (stdlib); mitmproxy addon + Playwright driver as **optional** guarded backends |
| catalog | `glyph.catalog` | SQLite store, flow→endpoint path templating, dedup, neutral `reachability` attribute |
| schema | `glyph.schema` | per-endpoint JSON inference, name-aware enum detection (genson optional, pure fallback) |
| **rosetta** | `glyph.rosetta` | **centrepiece** — sibling-pairing + DOM-attribute + reference-join strategies, noisy-OR confidence, review queue |
| fingerprint | `glyph.fingerprint` | backend family from Server/X-Powered-By/cookies |
| auth | `glyph.auth` | Bearer/Basic/API-key/cookie + HMAC-style request signing |
| gating | `glyph.gating` | rate-limit headers/429 + bot-mgmt vendor fingerprints (observation only) |
| codegen | `glyph.codegen` | OpenAPI 3 with `x-glyph-dictionary` meaning annotations |
| drift | `glyph.drift` | diff two catalogs — shape **and** meaning changes |
| mobile | `glyph.mobile` | static URL/API-path mining from an APK/IPA (stdlib zip+regex) |
| cli | `glyph.cli` | argparse entrypoint over all stages + `run har` pipeline |

## Design decisions this session

- **ADR-2** (accepted): monorepo, stages as packages, catalog as a library,
  SQLite → DuckDB → Postgres store path. Promoted from RESEARCH-DEEP-DIVE §7.1/§7.2.
- **ADR-3** (accepted): Glyph is fully standalone; supersedes ADR-1's InjectX
  clause. Reachability is a neutral catalog attribute, no sibling-project handoff.
- **Pure-stdlib base, heavy deps optional.** `import glyph` never requires
  mitmproxy/Playwright/genson/duckdb; the dependency-free capture path is HAR.
  This keeps the tool installable and testable anywhere.
- **User preference recorded:** modular packages over one long file — the code
  is structured as one subpackage per stage (see `user/preferences.md`).

## Baseline health

- `pytest`: **32 passed** (one focused test file per stage).
- `pip install -e .`: clean; `glyph --version` → `glyph 0.1.0`.
- Verified end-to-end: `glyph run har <file>` → capture→schema→rosetta;
  `glyph codegen`, `dict`, `fingerprint`, `auth`, `gating`, `drift`, `mobile`.

## Bug fixed mid-build

- **Single-sample enum gap.** A field named `status`/`type` with only one
  observed value was never flagged as an enum (the `total < 2` guard fired
  before the name allow-list), so DOM/sibling correlation couldn't decode a
  lone coded response. Fixed: allow-listed names qualify on a single sample;
  repetition/integer-range heuristics still require ≥2. (Surfaced by the DOM test.)
- **Auth signing false positive.** `api_key` leaked into `signing_params`
  because `"_"` was substring-matched as a nonce param. Nonce params now match
  exactly.

## Commits (this session)

`f4b4a9c` chore(context): shift to build mode + ADR-2 + ADR-3 →
`docs:` remove InjectX → `feat:` scaffold+catalog → `feat(capture)` →
`feat(schema)` → `feat(rosetta)` → `feat:` secondary stages → `feat(cli)` →
`test:` suite + enum fix → `docs:` README. See `git log` for the SHA range.

## Open items / recommended next steps

1. **HITL review UI** — `dict --review` lists low-confidence rows in the
   terminal; a proper review surface (Label Studio integration, per
   RESEARCH-DEEP-DIVE §4.6) is still a stub. Reference joins land at 0.85
   (below the 0.90 threshold) and always queue for review by design.
2. **DuckDB catalog backend** — the store interface is ready for the ADR-2
   promotion; not yet implemented (SQLite only).
3. **Rosetta depth** — Splink integration for probabilistic matching (§4.6)
   deferred; current confidence model is a hand-rolled noisy-OR. Consider
   positional/value-inferred correlation for APIs whose codes don't sit next
   to labels and don't appear in the DOM.
4. **Live capture E2E** — mitmproxy addon and Playwright driver are written
   but only import-tested (the `live` extra isn't installed in CI). Run a real
   `playwright install chromium` capture against an authorized target.
5. **Daraja callback verification recipe** (RESEARCH-DEEP-DIVE §3g) — a
   concrete early deliverable not yet started.
6. **Packaging** — no wheel built / no tag cut. `python -m build` when ready.
