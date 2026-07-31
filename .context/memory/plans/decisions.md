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

---
## ADR-4: Sensitive flagging — flag-and-keep, de-noise by tracking-vendor (2026-07-31)
- **Status:** accepted
- **Context:** The `glyph.sensitive` stage flags sensitive data, sensitive endpoints, and
  passive risk indicators. Two wrong instincts were corrected by the user during Session 10:
  (1) an initial plan to *redact* detected values by default — backwards for a
  reverse-engineering tool, where the captured value is the whole point; (2) a first noise
  model that hid *third-party* findings — wrong, because targets routinely store their own
  data on third-party CDNs/object stores (S3, `storage.googleapis.com`, Cloudinary), so
  hiding by party would bury real data exposure.
- **Decision:**
  1. **Flag and locate; keep the value intact at rest.** Findings store the real matched
     value. Glyph NEVER redacts captured data as a default. Redaction is an opt-in EXPORT
     concern only (for sharing a sanitized catalog/report), never a mutation of the working
     catalog.
  2. **De-noise by known tracking/ad vendor, never by first/third-party.** Sensitive-data
     findings (and unauthenticated-data / data-in-URL / verbose-error) are NEVER hidden, on
     any host. Only hygiene chatter (CORS, missing security headers) on a KNOWN analytics/ad/
     tracking vendor is hidden by default (`--all` shows it). CDNs and object stores are
     explicitly NOT vendors. First/third-party is retained as metadata, not a filter.
  3. **Passive only.** The stage analyzes already-captured traffic for authorized assessment.
     No active scanning, probing, or exploitation.
- **Consequences:** The catalog `findings` table holds live values — treat catalogs as
  sensitive artifacts (the user handles per-target legal/authorization, RESEARCH.md §10).
  `is_noise()` (host is a tracking vendor) drives the default view, not `party`. The vendor
  list (`sensitive/party.py::_TRACKING_VENDORS`) is the noise gate and is extensible. Related:
  Rosetta's reference-join is scoped to the same registrable domain so integer ids don't
  collide across unrelated hosts (`registrable_domain` in `catalog/normalize.py`).

---
## ADR-5: Split cli.py into a cli/ package; table rendering + masking for sensitive output (2026-07-31)
- **Status:** proposed
- **Context:** `glyph/cli.py` has grown to ~517 lines with 12+ subcommands. Two UX gaps
  surfaced in Session 11:
  1. **Inconsistent empty-state messaging:** `glyph run live` reports `rosetta: 0 decoded`
     (meaning rosetta ran but found nothing), yet `glyph dict` says `(dictionary empty — run
     'glyph rosetta' first)`, implying rosetta didn't run. The user has no way to tell
     whether rosetta needs to be re-run or legitimately found 0 candidates.
  2. **Sensitive findings are invisible:** `glyph sensitive` outputs only a count line
     (`sensitive: 10 finding(s) (2 medium, 8 low)`). The actual data is hidden behind a
     separate command with no at-a-glance visibility.
- **Decision:**
  1. **Split `glyph/cli.py` into `glyph/cli/` package.** One file per subcommand
     (`run.py`, `dict.py`, `rosetta.py`, `sensitive.py`, `codegen.py`, etc.), each exposing
     `add_parser(subparsers)` and `run(args)`. Shared helpers live in `_format.py` (table
     rendering, severity coloring, value masking) and `_output.py` (`--json` vs human
     output mode). Business logic stays in the stage modules; `cli/` is presentation only.
  2. **Fix empty-state consistency.** `glyph dict` must distinguish "rosetta ran and found
     nothing" from "rosetta hasn't run." If the catalog has a rosetta run logged, say so
     (timestamp, 0 results); otherwise suggest running it. Add a one-line hint about why
     0 fields were found (e.g., "no structured request/response bodies in captured flows").
  3. **Table output for `glyph sensitive`.** Masked values by default (show enough to
     identify: `sk_live_***3f2a`, not `[REDACTED]`), precise location (flow #, header/body/
     query/cookie), severity color-coding, and filter flags (`--severity`, `--type`, `flow N`).
     Add `--json` for scripting.
- **Consequences:** The CLI package grows from 1 file to ~8, but each is small and focused.
  The split makes it easier to add new commands (mobile, drift, fingerprint) without
  bloating a single file. Shared formatting in `_format.py` ensures consistent table look
  across `sensitive`, `dict`, and `schema` output. No business logic moves — the stage
  modules (`glyph.sensitive`, `glyph.rosetta`, etc.) remain the single source of truth.

- **Implemented:** 2026-07-31 (Session 12) — the `cli/` package split (one module per
  subcommand + `_shared`/`_output`/`_format`), the `dict` empty-state fix (via a `rosetta_ran`
  meta flag), and the `glyph sensitive` masked-table output all landed. Status → accepted.
  97 tests pass; `glyph.cli:main` / console script / `python -m glyph.cli` unchanged.
