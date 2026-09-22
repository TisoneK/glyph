# Session Review / Handoff — Sensitive stage + live-testing hardening (Session 10)

- **Date:** 2026-07-31
- **Agent:** Claude Code / claude-opus-4-8 (local, bao@local macOS)
- **Role:** engineer | **Core:** 0.4.0

## For the next agent — read this first

Glyph is a working general-purpose reverse-engineering toolkit (an installable Python
package, `glyph-re`). Pipeline stages, each a subpackage under `glyph/`, over one shared
SQLite catalog: **capture** (HAR + live Playwright), **catalog**, **schema**, **rosetta**
(code→meaning), **review** (HITL), **sensitive** (NEW this session), plus fingerprint, auth,
gating, codegen, drift, mobile. CLI entrypoint `glyph`. **97 tests pass.**

The through-line of this session: **real-world live captures against real sites** repeatedly
exposed bugs that the hand-authored tests could not. Honor that — see `user/preferences.md`
(real-world testing > curated tests; commit+push+.context automatically without being asked;
modular packages; redaction is opt-in EXPORT only, never at rest).

## What Session 10 delivered

1. **`glyph.sensitive` stage** — passive flagging over the captured catalog (no active
   scanning/exploitation):
   - `detectors.py` — PII/secrets/financial: email, phone (incl. Kenyan/M-Pesa), JWT,
     AWS/Google/Slack keys, private keys, passwords, credit cards (Luhn **+ card-network
     prefix 3-6**, after a Juice Shop timestamp false positive). Generic secrets gated on
     field name + entropy.
   - `endpoints.py` — path-based sensitive-endpoint classification (auth/admin/payment/
     account/credential/export/debug).
   - `risk.py` — passive risk indicators: secrets/PII in URLs, unauthenticated sensitive
     data, wildcard CORS, missing security headers, verbose errors, guessable-id (IDOR).
   - `party.py` — first/third-party + **tracking-vendor** classification.
   - Catalog `findings` table (kept value — never redacted; migration-safe).
   - `glyph sensitive` CLI (`--kind`, `--severity`, `--all`, `--party`, `--target`), and it
     runs **by default** at the end of `glyph run live` / `run har` (`--no-sensitive` to skip).

2. **Noise model correction (important).** First cut hid *third-party* findings; that was
   wrong — targets store their own data on third-party CDNs/stores. Corrected to **actionable
   vs tracking-noise**: sensitive-data findings are NEVER hidden on any host; only hygiene
   chatter (CORS/headers) on KNOWN tracking/ad vendors is hidden by default. CDNs/object
   stores are explicitly not vendors. See `is_noise()` in `sensitive/scan.py`.

3. **Rosetta reference-join scoped to registrable domain.** Flashscore exposed a global
   id→name index collision (sports `eventStageId=12` → cookie-consent `purposeId=12`).
   Now ids resolve only within the same registrable domain. `registrable_domain()` moved to
   `catalog/normalize.py` (shared; `sensitive/party` re-exports it).

## Live tests run this session (all via `glyph run live`, no scripts)

| Target | Result |
|---|---|
| linebet.com (via user's bore.pub proxy) | 919 flows, rich (earlier, Session 9) |
| demoblaze.com | 65 flows; thin Rosetta (codes are plain words) — good plumbing check |
| OWASP Juice Shop (heroku) | up briefly then 503 (dead demo); found real unauth admin-config |
| testphp.vulnweb.com | timeout (driver degraded gracefully, no crash) |
| **betika.com** (direct) | 318 flows; Rosetta decoded `sub_type_id 60→'1st Half 1x2'`; found unauth `/api/features/` leaking phone; exposed the third-party-noise problem |
| **flashscore.com** (direct, backgrounded) | 528 flows / 9 WS; exposed the reference-join cross-domain bug + flashscore.ninja signing surface |

## Environment (bao@local) — how to run live captures

- Unit tests: `.venv` (system Python **3.9.6**). `.venv/bin/python -m pytest -q`.
- **Live capture needs `.venv-312`** (Python 3.12.13 + Playwright 1.61; Chromium cached at
  `~/Library/Caches/ms-playwright`). Base `.venv` (3.9) has no Playwright.
  ```
  PYTHONPATH=/Users/bao/Code/glyph /Users/bao/Code/glyph/.venv-312/bin/python \
    -m glyph.cli run live "<url>" --explore N --settle-ms MS --db out.db
  ```
- `GLYPH_PROXY=<url>` env (or `--proxy`) routes the browser through an upstream proxy so
  credentials stay off the command line. The user's bore.pub tunnel is **ephemeral** —
  refresh before reuse.
- Flashscore-class heavy sites can exceed a 5-min foreground limit — run the capture in the
  background. The driver only persists flows after the browser closes.
- **mitmproxy cannot run here** — the sandbox classifier blocks a local proxy that upstreams
  to an authenticated tunnel (tried twice, not bypassable).

## Open follow-ups (also in `tasks/backlog.md`)

- **Tracking-vendor list is not exhaustive** — pixel/ad hosts (tapad, snapchat `tr.`, eskimi,
  inmobi, decibelinsight) still show as generic third-party. Extend `_TRACKING_VENDORS`.
- **`guessable_object_id` false positive on static asset paths** — fired on
  `decibelinsight.../{id}/{id}/di.js`. Skip non-API/static (`.js`,`.css`,img) paths.
- **Related-domain heuristic** — `flashscore.com` ↔ `lsapp.eu` / `flashscore.ninja` are the
  same org but different registrable domains, so they don't cross-join / are tagged
  third-party. A same-brand-label heuristic could recover these.
- **`build_dictionary` never clears stale entries** — a re-decode after a logic change keeps
  old rows. Consider a `--fresh` option (or clear-then-rebuild).
- **Public-by-design content** (T&C JSON on a CDN) flags contact info as sensitive — low
  value; consider de-prioritizing known public docs.
- **Retarget to Python 3.13 + Pydantic** (deferred by user); DuckDB backend; Splink/positional
  Rosetta depth; Daraja callback recipe; optional Label Studio review surface; mitmproxy-vs-
  Playwright live comparison (needs `mitmdump` allowed).

## Baseline

`pytest` → **97 passed**. `glyph` console script installs (`pip install -e .`). Tree clean,
`origin/main` synced.
