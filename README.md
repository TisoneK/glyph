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
glyph run live https://example.com    # capture → schema → rosetta → sensitive scan
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

### Browse mode — capture auth/payment/login flows (ADR-14)

Auto-capture drives the page with generic clicks and scroll, so it can't reach
anything behind a login wall, a payment form, a deposit/withdrawal flow, or a
multi-step wizard. **Browse mode** opens a VISIBLE browser that **you** drive —
log in, submit the deposit form, confirm the OTP — while Glyph captures every
request/response in the background. Same pipeline (schema → rosetta → sensitive
→ snihunt) runs after you stop.

Glyph attaches to **your real browser** (Brave/Edge/Chrome — all Chromium) so
your saved logins, password manager, and extensions carry over. No cert
install, no proxy setup.

```bash
# 1. Launch your browser with the debug port (one-time per session):
glyph browse --launch --browser brave --url https://target.example.com
#   (or launch it yourself: brave-browser --remote-debugging-port=9222 &)

# 2. Attach + capture. Ctrl+C detaches (your browser + tabs stay open):
glyph run live --browser https://target.example.com
# `--browse` is retained as an equivalent spelling; a browser name is optional:
glyph run live --browse https://target.example.com --browser brave
```

| Flag | Meaning |
|------|---------|
| `--browser [chrome\|msedge\|brave]` | enable continuous capture from your real Chromium browser; with no name it attaches to CDP, with a name it selects the launch fallback |
| `--browse` | equivalent legacy spelling for browser mode |
| `--cdp-port N` / `--cdp-host H` | CDP-attach endpoint (default `localhost:9222`; or set `GLYPH_CDP_URL`) |
| `--browser-path PATH` | explicit browser binary (Brave needs this if not auto-detected) |
| `--incognito` | launch-fallback only: fresh ephemeral context (no persistent profile) |

**Capture scoping (tab lineage):**

- `glyph run live --browse <url>` — Glyph opens a fresh tab for the target and
  hooks **that tab + popups only** (new tabs opened FROM it — payment providers,
  SSO, `target="_blank"`). Your other tabs (email, social, other-banking) are
  invisible to Glyph by construction.
- `glyph run live --browse` (no url) — **all-traffic mode**: hooks EVERY tab in
  the attached browser. The CLI prints a clear `⚠ browse-all` warning so it's
  never accidental. Flows are tagged by host; filter later with
  `glyph sensitive --target <host>` or `glyph target list`.

**Stop signal:**

- CLI CDP-attach mode: **Ctrl+C detaches** — the CDP connection drops, your browser
  and all its tabs stay open (closing your whole browser would be disruptive).
- TUI browser mode: press **`s` — Stop capture** (or confirm Quit). Glyph signals the
  capture worker; attached browsers stay open, while a browser Glyph launched is closed.
- Closing a launched browser also stops capture. The TUI continues refreshing until the
  capture reaches `done` and final analysis completes.

Notes:

- The browser must be **Chromium-based** (Chrome/Edge/Brave). Firefox/Safari
  have no CDP — use `glyph run har` (export a HAR from any browser) until a
  future `glyph capture proxy` (mitmproxy) lands.
- A persistent profile lives at `~/.glyph/profiles/<host>/` (launch-fallback
  only; CDP-attach uses your real profile). Log in once, all future runs on
  that host start already-authed.
- Brave's built-in Shields may block some requests; disable Shields for the
  target site if a capture looks incomplete.
- `glyph sensitive` will flag credentials/tokens/OTPs in the captured
  auth/payment flows — that's the point. Values are kept (the catalog is a
  sensitive artifact you own).

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
| `glyph run live --browser [<url>]` | continuous real-browser capture: you browse normally; stop with Ctrl+C or TUI `s` |
| `glyph run live --browse <url>` | equivalent browse-mode spelling; pipeline runs after detach/close |
| `glyph run har <file>` | run the full pipeline on a HAR |
| `glyph browse --launch` | spawn your browser with the CDP debug port for `--browse` |
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
| `glyph sensitive` | flag sensitive data, sensitive endpoints, and risk indicators |
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

## Sensitive & risk flagging

`glyph sensitive` scans what you've already captured and **flags and locates** — it never
removes the values it finds (this is a reverse-engineering tool; the value is the point).
Redaction, if you ever want it, is an opt-in *export* concern, never a default. It's passive
analysis for authorized assessment — no active scanning or exploitation.

```bash
glyph run live <url>               # the scan runs automatically at the end of a run
glyph sensitive                    # (re-)scan; actionable findings, most severe first
glyph sensitive --severity high    # only high/critical
glyph sensitive --kind risk        # just the risk indicators
glyph sensitive --all              # include tracking/ad hygiene noise too
```

**Noise, not third-party.** A page load pulls in analytics, ad, and CDN hosts alongside the
target. The line Glyph draws is *actionable vs noise*, **not** first-party vs third-party —
because a target's own data routinely lives on third-party hosts (S3, `storage.googleapis.com`,
Cloudinary, Firebase). So:

- **Sensitive data is never hidden, on any host** — PII on a CDN the target uses is exactly
  what you need to see.
- Only **hygiene chatter (CORS / missing headers) on known tracking-and-ad vendors** (Google
  Tag Manager, DoubleClick, adnxs, Hotjar, Clarity…) is treated as noise and hidden by default.
- CDNs and object stores are **not** noise.

Each finding is still tagged first-party / third-party (by registrable domain, multi-part TLDs
like `.co.ke` handled) and shows its host. `glyph sensitive` hides tracking noise by default;
`--all` shows it, `--party` filters by first/third, and `--target HOST` sets the primary host.

Three kinds of finding:

- **Sensitive data** — PII, secrets, and financial values in payloads/queries/headers
  (email, phone, JWT, API keys, private keys, passwords, credit cards via Luhn). The matched
  value is kept, with its exact location.
- **Sensitive endpoints** — classified by path (auth, admin, payment, account, credential,
  export, debug/internal).
- **Risk indicators** — secrets/PII carried in URLs, sensitive data on unauthenticated
  endpoints, wildcard CORS, missing security headers, verbose errors, and guessable object
  ids (IDOR/BOLA candidates).

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
