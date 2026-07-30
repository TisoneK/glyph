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
## ADR-1: Glyph is a standalone, general-purpose reverse-engineering toolkit (2026-07-29)
- **Status:** accepted
- **Context:** Reverse-engineering a new data source (web UI, API, mobile app, feed) repeats
  the same manual pipeline every time. We want a dedicated tool that automates the mechanical
  work and reduces semantic decoding to a confirm step.
- **Decision:** Build Glyph as its own repo/tool, NOT coupled to any product or data source
  (those are only *inputs* you point it at). Core thesis: automate the mechanical ~70%
  (capture, catalog, schema inference, gating profile, drift) and collapse the semantic ~30%
  via UI↔API correlation ("Rosetta"). Full scope, technique catalog, architecture, and phasing
  live in `RESEARCH.md`. Glyph defeats anti-bot, CAPTCHA, and access-control systems
  as a natural consequence of decoding them; it decodes payment-integration surfaces at the
  protocol/API level (tokenised payloads, not raw card values). Tunneling/relay routing is
  owned by the separate **InjectX** project.
- **Consequences:** Glyph stays domain-neutral — no product-specific logic in-repo. MVP =
  Capture → Catalog → Schema-infer → Rosetta + drift monitor (RESEARCH.md §8), gated behind a
  Phase-0 proof (§9).

---
## ADR-2: Monorepo with stages as packages over a shared catalog library (2026-07-30)
- **Status:** accepted
- **Context:** RESEARCH.md §11 asked whether Glyph should be one repo with stages as packages
  or a capture-tool + catalog-service split, and what the catalog store should be. Session 3's
  RESEARCH-DEEP-DIVE.md §7.1/§7.2 resolved both; this ADR promotes those resolutions to a
  standing decision now that the build has started (backlog item 3).
- **Decision:** Single Python package `glyph/` in one repo. Each pipeline stage is a submodule
  (`catalog/`, `capture/`, `schema/`, `rosetta/`, `auth/`, `gating/`, `fingerprint/`, `mobile/`,
  `codegen/`, `drift/`) plus a `cli.py` entrypoint. The **catalog is a library, not a service** —
  every stage reads/writes the same store in-process. Catalog store follows a three-step path:
  **SQLite (MVP) → DuckDB (when drift analytics matter) → Postgres (only when shared across
  users)**. Heavy capture backends (mitmproxy, Playwright) are **optional extras**, so the base
  package installs and its core (catalog/schema/rosetta) runs with a minimal dependency set; the
  dependency-free capture path is HAR ingestion.
- **Consequences:** No service boundary at MVP scale — single-process, debuggable. A service
  split is revisited only when the drift monitor must run on a schedule independent of capture,
  or multiple analysts share a catalog (both post-MVP). Core stages must not hard-import optional
  heavy deps at module load — guard them so `import glyph` works without Playwright/mitmproxy.

---
## ADR-3: Glyph is fully standalone — no coupling to sibling projects (supersedes ADR-1's tunneling clause) (2026-07-30)
- **Status:** accepted
- **Context:** ADR-1 named a separate "InjectX" project as the owner of tunneling/relay routing,
  and RESEARCH.md §11 / RESEARCH-DEEP-DIVE.md §7.4 carried an open "handoff line to InjectX"
  question. The user directed (2026-07-30): *"remove injectx framing here it contaminates the
  project"* — consistent with the standing preference (Session 1 correction): *"do NOT couple a
  standalone tool to sibling projects."*
- **Decision:** Glyph names no sibling project anywhere in its framing, docs, or code. The
  reachability of a decoded endpoint is a **neutral, Glyph-internal catalog attribute**
  (`reachability: direct | needs_tunnel | unreachable`, plus an optional free-text
  `reachability_note`) that simply records what Glyph observed — it hands off to nothing and
  names no external tool. Whatever an analyst does with an unreachable endpoint is outside
  Glyph's scope and outside its vocabulary.
- **Consequences:** Supersedes the final sentence of ADR-1's Decision ("Tunneling/relay routing
  is owned by the separate InjectX project") — that clause is void. Product docs (RESEARCH.md,
  RESEARCH-DEEP-DIVE.md) are edited to drop InjectX naming. Append-only history that mentions
  InjectX (past session/review logs) is left intact as an accurate record of what was true then.
