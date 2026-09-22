# Session 29 — Endpoint data view and cross-platform TUI reliability

## Scope

Implemented the requested endpoint-data surface and investigated the Mac/Windows live-TUI symptoms: empty top-bar statistics, delayed tab population, and Rosetta appearing empty after parallel analysis.

## Product changes

- Added a **Data** dashboard tab and `endpoint_data_rows()` adapter. It lists only endpoints with response bodies and shows method, normalized endpoint, payload type, content encoding, size, status, response-header names, and a clipped preview. JSON, HTML/XML/text, gzip, ZIP, and generic/binary payloads are recognized using both metadata and magic bytes; base64-wrapped HAR binary bodies are classified without changing stored data.
- Added a `DATA` headline count for body-bearing endpoints. Data refresh remains live and uncached. The dashboard refreshes only the active tab during capture and reloads every view on completion or tab activation.
- Persisted capture errors in `capture_error` for auto and browse capture paths. The live dashboard now guards startup/catalog reads, surfaces capture and analysis failures in the header, records analysis status/error metadata, retries final analysis around transient SQLite contention, and avoids starting SNI when core analysis fails. Worker completion reloads are safe during screen teardown.
- Preserved the pipeline dependency contract: schema inference and Rosetta remain chained in one lane; sensitive scanning runs beside that lane. This prevents Rosetta from reading a schema that has not completed. SNI remains outside the core pool.

## Caching decision

No response/data cache was added. A cache would make newly captured rows look absent on Windows and could display stale Rosetta/data state while SQLite is changing. WAL reads plus active-tab-only refresh already reduce UI work without sacrificing freshness.

## Validation

- Focused TUI/pipeline/capture suite: **40 passed, 1 skipped**.
- Full suite: **181 passed, 5 skipped**.
- `compileall` and `git diff --check`: passed.
- Product commit: `df80a3e` (`feat(tui): add endpoint data view and live diagnostics`).

## Remaining follow-ups

- Verify the real Playwright live dashboard on the user’s Windows machine, including a non-empty top bar, streaming Data rows, and Rosetta rows after finalization.
- Consider a bounded shutdown timeout/fallback for pathological browser/network hangs; current shutdown remains intentionally graceful.
