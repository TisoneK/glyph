# Architectural Decisions (append-only, ADR-style)

Decisions already made — future agents respect these rather than
relitigating them. To reverse one, append a new ADR that supersedes it.

<!-- TEMPLATE — copy below the last entry:
---
## ADR-N: <short title> (YYYY-MM-DD)
- **Status:** accepted | superseded by ADR-M
- **Context:** <what forced the decision>
- **Decision:** <what was decided>
- **Consequences:** <trade-offs accepted; what future agents must respect>
-->

---
## ADRs still in force (re-seeded at the office-001 close)

The decisions below were made in the frozen office and remain binding. Their
full text lives in `history/office-001/plans/decisions.md`; they are restated
here in one line each so a fresh session can resolve the numbers the code and
docs cite without reading a frozen office. New decisions append below this
block as `ADR-25` onward.

| ADR | Decision |
|-----|----------|
| 1 | Glyph is a standalone, general-purpose reverse-engineering toolkit (partly superseded by ADR-3). |
| 2 | Monorepo: pipeline stages as subpackages over a shared catalog library. |
| 3 | Fully standalone — no coupling to sibling projects. |
| 4 | Sensitive flagging: flag-and-keep, de-noised by tracking-vendor. |
| 5 | `cli/` package split; table rendering plus masking for sensitive output. |
| 6 | Capture operates at the HTTP/application layer; raw packet capture is out of core. |
| 7 | Mobile static mining covers the whole package family (APK/IPA + XAPK/APKS/APKM + OBB). |
| 8 | `rich` is the CLI rendering layer and the base package's one runtime dependency. |
| 9 | The TUI is a presentation layer over `glyph.db`; the engine stays headless. |
| 10 | SNI bug-host hunting is a bounded active-recon stage, run after sensitive. |
| 11 | VPN-config decoding is file-triggered and lives behind the `[crypto]` extra. |
| 12 | Multi-target catalog: a `targets` table plus a `target_id` on every data row. |
| 13 | Browse mode via Playwright persistent context (superseded by ADR-14). |
| 14 | Browse mode: CDP-attach to the user's real browser is primary; a launched Chromium is the fallback. |
| 15 | Analysis stages run concurrently as a parallel pipeline, with schema→rosetta chained. |
| 16 | The current target is persisted and restored for display commands. |
| 17 | TUI stage selection; screen CSS lives on the App class (a default screen's CSS never loads). |
| 18 | TUI quit lifecycle, detached SNI lane, and switching among processed targets. |
| 19 | Endpoint-data view and live TUI freshness. |
| 20 | Continuous real-browser capture with TUI-controlled detach. |
| 21 | Cross-platform quit confirmation and a coordinated SNI lane. |
| 22 | Pumped real-browser capture lifecycle (sync Playwright objects need pumping). |
| 23 | Geo-block recovery and explicit browser targeting. |

## ADR-24: The protocol is core 2.0.3 — `ledger-*` tools, office layout (2026-09-23)

- **Status:** accepted
- **Context:** The vendored core was 0.8.0 while the package upstream is at
  2.0.3, and the 0.8.0 `context-sync verify` failed on this Windows machine on
  every core file (LF-only manifest vs a CRLF checkout). The protocol itself
  had moved on to the office architecture.
- **Decision:** Migrate to core 2.0.3 — `ledger-sync update --major`, then
  `migrate` (live-office grouping, backfill, LF normalization), then `rename`
  (`.context/` → `.context_ledger/`). All protocol tooling is now the
  `ledger-*` family; memory lives under `memory/office/`, with the durable
  zones at the memory root.
- **Consequences:** The protocol surface commits as `chore(ledger):`.
  Sessions check in on `memory/office/agents/roster.md` before the deep read
  and close a full office (`ledger-history close`) at the door. The recursive
  `.gitattributes` that arrives with 2.x keeps core files LF on every
  platform, retiring the CRLF verify trap. Windows gates cannot pass
  `ledger-sync verify` until the package fixes two unparseable `.ps1` ports
  (see `flaws/log.md`, 2026-09-23).
