# Glyph

A standalone, general-purpose **reverse-engineering toolkit**. Point it at a target —
a web app, a JSON/gRPC API, a mobile app, a data feed — and it does the mechanical work
of discovering, capturing, decoding, and documenting that target's surface, so a human
only has to confirm the ambiguous parts.

The name: the tool decodes a target's opaque symbols (codes, ids, enums) into meaning,
the way a glyph is a mark that carries meaning once you can read it.

**Status:** early alpha — the base package is built and tested. Full scope, technique
catalog, and research live in **[RESEARCH.md](RESEARCH.md)** and
**[RESEARCH-DEEP-DIVE.md](RESEARCH-DEEP-DIVE.md)**.

## Install

The base package is pure-stdlib — no third-party dependencies required:

```bash
pip install -e .
```

Optional extras: `pip install -e '.[live]'` (mitmproxy + Playwright live capture),
`.[schema]` (genson), `.[analytics]` (DuckDB), `.[dev]` (everything + pytest).

## Quickstart

Glyph works on **any** target — capture a session as a HAR (from browser devtools,
mitmproxy, Charles, Proxyman), then run the pipeline:

```bash
glyph run har session.har          # capture -> catalog -> schema -> rosetta
glyph dict                         # the decoded code -> meaning dictionary
glyph dict --review                # only rows needing a human confirm
glyph codegen --out openapi.json   # OpenAPI 3 spec (meanings annotated inline)
glyph fingerprint                  # backend family from response signals
glyph auth                         # auth schemes + request signing
glyph gating                       # rate-limit + bot-management signals
glyph drift before.db after.db     # what changed between two snapshots
glyph mobile app.apk               # mine endpoints/URLs from a mobile package
```

Every catalog command takes `--db PATH` (default `glyph.db`); analysis commands take
`--json`. The pipeline is a set of composable stages over one shared SQLite catalog
(**ADR-2**), each importable as a library (`from glyph.rosetta import build_dictionary`).

## Pipeline

| Stage | Package | What it does |
|-------|---------|--------------|
| capture | `glyph.capture` | ingest observed traffic (HAR; optional live proxy/browser) |
| catalog | `glyph.catalog` | the shared SQLite store every stage reads/writes |
| schema | `glyph.schema` | infer a JSON Schema per endpoint, flag enum candidates |
| **rosetta** | `glyph.rosetta` | **decode opaque codes -> meaning with confidence scores** |
| fingerprint | `glyph.fingerprint` | identify the backend family |
| auth | `glyph.auth` | classify authentication + request signing |
| gating | `glyph.gating` | profile rate-limiting + bot-management (observation only) |
| codegen | `glyph.codegen` | emit an OpenAPI 3 spec |
| drift | `glyph.drift` | diff two catalog snapshots (shape **and** meaning) |
| mobile | `glyph.mobile` | static endpoint/URL mining from an app package |

> **A note on security and payment surfaces** — Glyph defeats anti-bot, CAPTCHA,
> and access-control systems as a natural consequence of decoding them. It handles
> payment-integration surfaces at the protocol/API level (tokenised payloads, not
> raw card values). Credential and card values are never stored or logged. Use it only
> against targets you are authorized to analyze.

## Working with this repo

This repo uses the `.context/` protocol — persistent agent memory plus a vendored copy of
the workflow, committed to git. Any agent starts at
**[.context/kickoff.md](.context/kickoff.md)**.
