# Glyph

> Point Glyph at a target — a web app, a JSON API, a mobile app — and it captures,
> catalogs, and **decodes** that target's surface: turning opaque codes, ids, and enums
> into documented meaning, so you only confirm the ambiguous parts.

Reverse-engineering an unfamiliar API is the same manual loop every time: capture the
traffic, work out the endpoints, guess the schemas, and stare at the UI to figure out what
`status: 3` actually *means*. Glyph automates the mechanical majority of that and collapses
the semantic part — "what does this code mean?" — into a quick confirm step.

The name says the goal: a glyph is a mark that carries meaning once you can read it. Glyph
reads a target's marks.

## Features

- **Capture from anywhere** — ingest a HAR exported from browser DevTools, mitmproxy,
  Charles, or Proxyman. No proxy or browser needed for the core workflow.
- **Automatic cataloging** — collapses concrete URLs into endpoints
  (`/users/123` → `/users/{id}`), dedupes, and stores everything in one queryable catalog.
- **Schema inference** — a JSON Schema per endpoint, with enum-like fields flagged for you.
- **Rosetta decoding** — the centerpiece: correlates opaque API codes with the
  human-readable labels they map to, emitting a `code → meaning` dictionary with confidence
  scores and evidence.
- **Human-in-the-loop review** — confirm, edit, or reject uncertain decodings; your
  decisions become ground truth and survive re-runs.
- **OpenAPI export** — generate an OpenAPI 3 spec with decoded meanings annotated inline.
- **Surface analysis** — identify the backend stack, authentication and request-signing
  schemes, and rate-limiting / bot-management defenses.
- **Drift tracking** — diff two captures over time to catch not just shape changes but
  *meaning* changes.
- **Mobile triage** — statically mine endpoints and URLs out of an APK or IPA.

## Install

Requires Python 3.9+. The core is pure-Python with no required dependencies:

```bash
pip install -e .
```

Optional extras:

| Extra | Adds |
|-------|------|
| `live` | live capture via mitmproxy + Playwright |
| `schema` | higher-fidelity schema inference (genson) |
| `analytics` | columnar catalog store (DuckDB) |
| `dev` | everything above, plus pytest |

```bash
pip install -e '.[live]'
```

## Quickstart

Two ways in. **Live** — Glyph drives a real headless browser and captures everything itself
(needs the `live` extra):

```bash
glyph run live https://example.com    # drive the page → capture → schema → rosetta
```

Or from a **HAR** you already have (browser DevTools → Network → *Export HAR*, mitmproxy,
Charles…):

```bash
glyph run har session.har
```

Either way, inspect and export the same way:

```bash
glyph dict                        # see the decoded code → meaning dictionary
glyph review                      # confirm/edit/reject the uncertain rows
glyph codegen --out openapi.json  # export a documented OpenAPI 3 spec
```

That's the golden path. Every command that reads or writes a catalog takes `--db PATH`
(default `glyph.db`).

### Live capture

`glyph capture live <url>` (and `glyph run live <url>`) drives a headless browser and is
**site-agnostic** — no per-site configuration or scripts. It records *every* kind of traffic
automatically (documents, scripts, XHR/fetch, WebSocket frames, …), snapshots the rendered
DOM for Rosetta, and runs a few target-agnostic interaction rounds (scroll, generic clicks)
to surface lazy-loaded endpoints.

```bash
glyph capture live https://example.com                 # sensible defaults, any site
glyph capture live https://example.com --explore 5     # richer: more interaction rounds
glyph capture live https://example.com --proxy http://host:port   # route via a proxy
GLYPH_PROXY=http://host:port glyph capture live https://example.com  # proxy via env
```

| Option | Meaning |
|--------|---------|
| `--explore N` | target-agnostic interaction rounds (default 2) |
| `--settle-ms N` | quiet wait after load for late XHR (default 3000) |
| `--wait-selector CSS` | wait for a selector that marks "content settled" |
| `--proxy URL` / `GLYPH_PROXY` | route the browser through an upstream proxy |
| `--timeout-ms N` | per-step timeout (default 30000) |

## How Rosetta works

Most APIs return codes whose meaning lives only in the rendered UI. Glyph recovers that
mapping automatically, using several strategies and scoring each result:

- **Sibling fields** — an object carrying both `{"status": 3, "status_label": "Shipped"}`
  (or the generic `{"type": 2, "name": "Premium"}`) hands you the mapping directly.
- **Rendered labels** — a code that appears in the DOM next to its label, such as
  `<span data-status="3">Shipped</span>`, harvested at capture time.
- **References** — a `user_id` that resolves to the matching user object's name elsewhere
  in the catalog.

Each candidate gets a confidence score, and agreement between strategies raises it. Anything
below the bar is queued for review rather than asserted:

```text
$.orders[].status   3 → "Shipped"   conf 0.97  sibling
$.orders[].status   1 → "Pending"   conf 0.95  dom_attr
$.comments[].user_id 5 → "Alice"    conf 0.85  reference   [review]
```

Glyph narrows the problem; you make the final call on the ambiguous cases:

```bash
glyph review                     # interactive: [c]onfirm [e]dit [r]eject [s]kip
glyph review --auto-confirm 0.9  # trust the model above a threshold, review the rest
glyph review --stats             # progress
```

Confirmed and edited entries become ground truth — a later `glyph rosetta` never overwrites
them.

## Commands

| Command | Purpose |
|---------|---------|
| `glyph run live <url>` | drive a live page, then the full pipeline |
| `glyph run har <file>` | run the full pipeline on a HAR |
| `glyph capture live <url>` | drive a live page and capture everything |
| `glyph capture har <file>` | ingest traffic only |
| `glyph schema` | infer schemas and flag enum candidates |
| `glyph rosetta` | decode codes → meaning |
| `glyph dict [--review]` | show the decoded dictionary |
| `glyph review` | confirm / edit / reject decodings |
| `glyph codegen [--out FILE]` | emit an OpenAPI 3 spec |
| `glyph fingerprint` | identify the backend stack |
| `glyph auth` | authentication and request signing |
| `glyph gating` | rate-limiting and bot-management signals |
| `glyph drift <a.db> <b.db>` | diff two catalog snapshots |
| `glyph mobile <app.apk>` | mine endpoints from a mobile package |
| `glyph catalog` | summarize the catalog |

Analysis commands accept `--json` for machine-readable output.

## Use it as a library

Every stage is importable — the catalog is the integration point:

```python
from glyph.catalog import Catalog
from glyph.capture import ingest_har
from glyph.schema import infer_all
from glyph.rosetta import build_dictionary

cat = Catalog("glyph.db")
ingest_har(cat, "session.har")
infer_all(cat)
build_dictionary(cat)

for entry in cat.dictionary():
    print(entry.json_path, entry.code, "→", entry.meaning)
```

## Architecture

Glyph is a set of composable stages over one shared catalog. Each stage is an independent
subpackage; the catalog is a plain SQLite database, with a promotion path to DuckDB or
Postgres for larger workloads.

```
capture → catalog → schema → rosetta → review
                       ↘ fingerprint · auth · gating · codegen · drift · mobile
```

```
glyph/
├── catalog/     shared store (models, SQLite, URL normalization)
├── capture/     HAR ingestion + label harvesting (+ optional live backends)
├── schema/      JSON Schema inference + enum detection
├── rosetta/     code↔meaning correlation, confidence, dictionary
├── review/      human-in-the-loop confirmation
├── fingerprint/ · auth/ · gating/ · codegen/ · drift/ · mobile/
└── cli.py       the `glyph` command
```

## Status

Glyph is early and evolving. The full pipeline — capture, catalog, schema, Rosetta decoding,
review, and OpenAPI export — works today; the HAR path needs no external dependencies, and
live browser capture is a first-class command behind the optional `live` extra. Interfaces
may still change as Glyph is exercised against more real targets.

## Responsible use

Glyph decodes access-control, anti-bot, CAPTCHA, and payment surfaces as a natural
consequence of documenting them. It works at the protocol / API level and never stores or
logs credential or card values. Use it only against targets you own or are explicitly
authorized to analyze, and respect their terms and rate limits.

## Development

```bash
pip install -e '.[dev]'
pytest
```

The codebase is deliberately modular — one subpackage per stage, each independently
testable. Design background lives in [RESEARCH.md](RESEARCH.md).

## License

MIT.
