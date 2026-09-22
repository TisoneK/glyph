# Session Review / Handoff — SNI bug-host hunting stage (Session 16)

- **Date:** 2026-07-31
- **Agent:** Super Z / unknown (cloud sandbox, Python 3.12.13)
- **Role:** engineer | **Core:** 0.4.0

## For the next agent — read this first

Glyph is a general-purpose reverse-engineering toolkit (`glyph-re`). Pipeline
stages over one shared SQLite catalog: capture → catalog → schema → rosetta →
sensitive → **snihunt (NEW this session)**, plus fingerprint, auth, gating,
codegen, drift, mobile, review, TUI. CLI entrypoint `glyph`. **123 tests pass**
(was 106; +17 new SNI tests), 3 skipped (textual not installed in this sandbox).

The user's directive: add an SNI bug-host hunting feature that finds NEW hosts
by reverse-domain / Cloudflare techniques — explicitly NOT scraping published
`bughost.txt` lists. It must auto-run after `sensitive` when a user enters a
target on `glyph run live`, and a new TUI tab must show the candidates.

## What Session 16 delivered

1. **ADR-10 (proposed → accepted/implemented).** `glyph.snihunt` is the ONE
   bounded active-recon stage (every other stage is passive over the captured
   catalog, per ADR-4). The scope fence: read-only public APIs (DNS, CT logs,
   reverse-IP) + an opt-in active SNI probe that opens ONE TLS handshake to a
   public CDN edge (exactly what a browser does — no port scanning, no
   exploitation). Authorization stays with the user (RESEARCH.md §10); Glyph
   surfaces candidates only and names no tunneling tool (ADR-3).

2. **`glyph/snihunt/` package** — 8 modules:
   - `extract.py` — pull every SNI/host + captured IP from the catalog (pure).
   - `dns.py` — DoH resolution (Google `dns.google` + Cloudflare `cloudflare-dns.com`),
     cached, with a `socket.getaddrinfo` system fallback.
   - `reverseip.py` — HackerTarget `reverseiplookup` API for sibling hostnames
     sharing an IP (the "reverse-domain" technique the user named).
   - `ctlogs.py` — Certificate-Transparency subdomain enumeration (certspotter
     primary, crt.sh fallback; per-domain cap 500, 429-aware). This is the
     "find NEW hosts" path — subdomains that have ever held a cert but weren't
     in the capture.
   - `cdn.py` — Cloudflare (AS13335) / Fastly / Akamai / CloudFront edge
     detection via embedded IPv4/IPv6 ranges + hostname suffixes. Works offline
     over captured IPs.
   - `zerorate.py` — zero-rating heuristics: Facebook Free Basics, Wikipedia
     Zero, internet.org, Opera Mini, common free-pack patterns. Conservative —
     only tags hosts matching a known program (false positives waste the user's
     tunnel test).
   - `probe.py` — optional active SNI TLS handshake (default OFF); records the
     served cert's CN/SAN.
   - `hunt.py` — orchestrator: discovery phase (extract → CT → resolve →
     reverse-IP) then scoring phase (0-100, weighted: CDN +30, zero-rate +30,
     shared cert +15, wildcard +10, reverse +10, captured +10, probe +10),
     persists top N as `Finding(kind="sni_bug_host")`. Idempotent; kind-scoped
     clear so sensitive findings survive a re-run.

3. **Catalog:** new `FINDING_SNI_BUG_HOST = "sni_bug_host"` kind (free TEXT
   column — no schema migration). `Catalog.clear_findings(kind=...)` now accepts
   an optional kind filter. `sensitive/scan.is_noise` treats `sni_bug_host` as
   never-noise (the point of the stage, like sensitive-data findings).

4. **CLI:** `glyph snihunt [--db] [--target] [--no-net] [--probe] [--min-score]
   [--max-domains] [--json]`. Auto-runs after `sensitive` in `glyph run live` /
   `run har`; `--no-snihunt` opts out (independent of `--no-sensitive`). The
   `run` summary panel gains an `snihunt` row.

5. **TUI:** new tab key 6 "SNI Hunt" with `D.snihunt_rows(cat)` (SEV / SCORE /
   TYPE / SNI HOST / EVIDENCE). The summary bar adds an SNI candidate count.
   The live dashboard runs the hunt ONCE at `_finalize` (not on every 4s
   analyze tick — it does network recon that would be too slow/chatty to repeat).

6. **Tests:** 17 new offline tests (`tests/test_snihunt.py`) with a swappable
   `http_get` fake — extract, CDN detect (IP + suffix), zero-rate patterns,
   CT enumeration, hunt orchestration (discovery + scoring), idempotency,
   kind-scoped clear, TUI adapter, CLI. Existing `run har` tests pass
   `--no-snihunt` to stay fast/offline. **123 pass, 3 skipped.**

## Real-world verification (live, not synthetic)

Ran the stage against a 2-host capture (`cloudflare.com` + `0.facebook.com`):
- **184 candidates discovered** in ~66s.
- `0.facebook.com` scored **75 (high)**: zero-rated (facebook_free_basics) +
  wildcard cert + 144 CT subdomains + 2 reverse-IP siblings.
- `cloudflare.com` scored **50 (medium)**: captured + Cloudflare-fronted + 20
  reverse-IP siblings.
- **21 Cloudflare-fronted candidates** found via reverse-IP (the reverse-domain
  technique): `ajax.cloudflare.co`, `cdnjs.cloudflare.at`,
  `developers.cloudflare.co`, etc. — sibling hostnames sharing Cloudflare's
  edge IPs.
- 3 zero-rated, 158 shared-cert (CT) candidates.

This is exactly the "find a NEW host by reverse-domain, cloudflare" capability
the user asked for. Sources consulted (not scraped): Wireshark SNI-field
walkthroughs, YouGetSignal reverse-IP, crt.sh / certspotter CT APIs, Cloudflare
domain-fronting literature (digi.ninja, Praetorian, Zscaler).

## Design decisions worth noting

- **Discovery vs scoring separation.** First cut interleaved reverse-IP into
  the scoring loop, which mutated `candidates` mid-iteration. Refactored into
  a clean two-phase: discovery (extract → CT → resolve → reverse-IP, building
  the full candidate set including siblings) THEN scoring (snapshot, no
  mutation). One level deep — siblings-of-siblings aren't chased (run again to
  go deeper).
- **`--no-net` is a first-class mode.** The stage always runs SOMETHING useful:
  with `--no-net` it does local heuristics only (extract + embedded CDN ranges
  + zero-rating patterns over the captured surface). Online path enriches with
  DoH + CT + reverse-IP. Tests run fully offline via a swappable `http_get`.
- **The probe is opt-in.** Default OFF keeps the stage read-only recon. The
  user opts in with `--probe` when they want cert-lineage verification. The
  probe does NOT verify carrier zero-rating (that needs the user's SIM on the
  target network — tracked as a backlog follow-up).
- **crt.sh is the fallback, not primary.** In practice crt.sh is slow/timeout-
  prone (confirmed during research). certspotter is the primary CT source;
  crt.sh is the secondary. Both are bounded and graceful.

## Open follow-ups (also in `tasks/backlog.md`)

- **Live carrier verification** — the stage surfaces CANDIDATES; it does not
  verify a candidate actually passes a specific carrier's DPI as zero-rated.
  An optional on-device recipe (open a TLS tunnel through the carrier, measure
  whether bytes flow without data balance dropping) is tracked as a follow-up.
- **Enrich the zero-rating TLD/pattern set** — the global free surfaces (Free
  Basics, Wikipedia Zero, internet.org) ship now; Kenya/East-Africa carrier
  free-pack domains (Safaricom/MTN/Airtel) rotate and are operator-specific —
  extend `_ZERO_RATED_PATTERNS` as live hits are confirmed.
- **Third CT-log source** — certspotter + crt.sh cover most cases; a third
  (Google CT search, Censys) would harden enumeration if both are down.

## Environment (this sandbox)

- Python 3.12.13 (`/home/z/.venv/bin/python3`). `rich` IS installed in this
  venv (the CLI renders rich tables); `textual` is NOT (3 TUI tests skip).
- Outbound network: Google DoH, Cloudflare DoH, HackerTarget reverse-IP, and
  certspotter CT all reachable. crt.sh times out (slow/overloaded) — kept as
  fallback only.
- The PAT was passed in chat; stripped from `.git/config` immediately after
  clone. All pushes go through `/home/z/my-project/scripts/glyph_push.py`,
  which reads the token from a gitignored file and pushes a one-shot URL (token
  never touches `.git/config` or the bash command line — per Session 7's
  lesson on credentials + the content filter).

## Baseline

`pytest` → **123 passed, 3 skipped** in 0.87s. `glyph snihunt` CLI verified
(rich table on a real catalog). Tree clean, `origin/main` synced (commits
`49e4fbe` chore(context) + `0ff9e7d` feat(snihunt)).
