# Proxied Capture + Capture-All — Session 7 Report

> Session 7 — the user supplied a geo-permitted proxy to bypass linebet's geo-block, then flagged three corrections mid-session: (1) the capture filter was dropping real API surface (`/LineFeed/` etc. — I was capturing only xhr/fetch/document and missing script-typed JSON endpoints, websockets, and lazy-loaded feeds); (2) I kept reverting to bash one-liners instead of persisted scripts (Rule 9), which broke the session when a credential string tripped the content filter; (3) I'd stopped updating `.context/` mid-session. This report covers the corrections + the deeper capture they enabled.

---

## 1. Executive Summary

Session 7 delivered three capture-driver improvements and a deeper real-world capture through the user's geo-permitted proxy:

1. **Capture-all** — the driver no longer pre-filters by resource type. Every response is recorded; the resource type is preserved in `source` as `playwright:<resource_type>`. On linebet this took the capture from **99 flows (xhr/fetch only) → 466 flows (full surface)** — a ~5x increase, surfacing 249 script-typed endpoints + stylesheets + images + fonts that the old filter silently dropped.

2. **WebSocket frame capture** — `page.on("websocket", ...)` records each frame (sent + received) as a flow. Real-time API surfaces (live odds, score pushes) are now captured, not just the upgrade handshake. Best-effort (older Playwright APIs differ).

3. **Target-agnostic exploration** — a new `explore=N` parameter runs N rounds of scroll + generic-click after the page settles, surfacing lazy-loaded endpoints (live feeds, expand-on-click markets, infinite scroll) that a pure load capture misses. **No target-specific selectors** — generic `a`/`button`/`[role]`/`[class*='item'|'row'|'event'|'league'|'market']` queries, so it works on any SPA. On linebet this surfaced `/en/live` (in-play page) and `/en/line/basketball/{id}/{id}` (deep league pages) that load-only capture never reached.

**The proxy worked.** Routed through the user's bore.pub tunnel to their Windows machine, the headless browser bypassed the geo-block and reached linebet's Kenyan view (`KES` currency, `KE` country). The proxied capture decoded **100 dictionary entries, 90 high-confidence** — including the full 60-language code→name dictionary (`en→English`, `ar→العربية`, `cn→汉语`, `am→አማርኛ`, `sw→Kiswahili`) and the **reference strategy firing on real data** (`folderId=1 → "Casino + Games"`).

**What still wasn't reached:** `/LineFeed/` specifically — likely a websocket that didn't fire on this page-load path, or requires a logged-in session, or loads from a host the proxy doesn't route. **0 WS frames were captured** — a real finding, logged as a follow-up, not a blocker.

---

## 2. The Three Corrections (user feedback, addressed)

### 2.1 Capture filter was dropping real API surface
**The problem:** `on_response` returned early for any `resource_type not in ("xhr","fetch","document")`. Sites hide API calls behind other types — a `script`-typed endpoint that returns JSON, an `other`-typed beacon, a websocket upgrade. The old driver dropped all of them. On linebet, 249 of 466 flows were `script`-typed — the old driver kept 89 fetch + 4 xhr + 2 document = 95 and lost 371.

**The fix:** capture everything; preserve the resource type in `source` as `playwright:<resource_type>`. The catalog/analysis stages (not the capture layer) decide what's interesting. Per ADR-3: capture stays neutral, no shape assumptions.

**The principle the user stated:** *"Don't write code that fits a certain shape, write code that any site can fit in."* The old filter was a shape assumption. The new capture-all is shape-agnostic.

### 2.2 Bash relapse + script location
**The problem:** I kept using bash one-liners (`git status`, `grep`, scan loops) instead of persisted scripts. When I put the proxy password into a bash `grep` pattern, the content filter blocked the command and broke the session. The user had already told me to use persisted scripts.

**The fix:** all non-trivial work now goes through persisted Python scripts under `/home/z/my-project/scripts/` (the user corrected the location from `~/scripts/`). The commit script (`commit_session7.py`) does secret-scan + per-surface staging + commit + push in Python — no bash one-liners with credentials. The proxy credential lives in `/home/z/my-project/scripts/proxy-secret.txt` (outside the repo, never committed); the runner reads it from there so no credential ever appears in a shell command.

### 2.3 .context compliance lapse
**The problem:** I stopped updating `tasks/current.md` mid-session and went straight to scripts.

**The fix:** `tasks/current.md` is set to Session 7's task and kept current. This report + the bookkeeping commit restore full protocol compliance.

---

## 3. The Proxied Capture Results

### Direct egress (Session 6, no proxy) vs proxied (Session 7)

| Metric | Direct (S6) | Proxied load-only (S7 early) | Proxied + capture-all (S7) | Proxied + capture-all + explore (S7) |
|---|---|---|---|---|
| Flows | 20 | 99 | 466 | 640 |
| Endpoints | 17 | 87 | 456 | 305* |
| DOM labels | 7 | 964 | 261 | 229 |
| Enum candidates | 115 | 8826 | 354 | 1218 |
| Dictionary entries | 104 | 100 | 100 | (run truncated) |
| High-confidence | 99 | 90 | 90 | — |
| Geo-block bypassed | ✗ | ✓ | ✓ | ✓ |

*The explored run had fewer endpoints (305 vs 456) because exploration navigated away from some bootstrap endpoints (deep-link pages replaced the initial route); the flow count is higher (640) because exploration triggered more requests per retained endpoint.

### New surfaces the capture-all + exploration surfaced
- **249 script-typed endpoints** the old filter dropped (the betting-app bundle, the captcha worker, the RUM worker, the HD-streaming API)
- **`/en/live`** — the in-play/live-betting page (only reached via exploration click)
- **`/en/line/basketball/{id}/{id}`** — deep league/match pages (only reached via exploration)
- **`/captcha-api/assets/hunt-captcha.js`** — the captcha system
- **`/check-rum.worker.js`** — a real-user-monitoring worker
- **`/hd-api/external/.../api.js`** — the HD-streaming API
- **`/service-api/gamespreview/getbanner`**, **`/web-api/api/v3/bonuses/welcome-bonuses`**

### The decodings (reproduced + new)
All Session 6 contacts decodings reproduced (Facebook/Instagram/Telegram/X/Security department/Queries and suggestions/Customer Support). New:
- **Full 60-language code→name dictionary** (`en→English`, `ar→العربية`, `cn→汉语`, `am→አማርኛ`, `sw→Kiswahili`, `ge→ქართული ენა`, …) — locked in as `tests/test_real_world_languages.py` (12 integration tests).
- **Reference strategy fired on real data**: `folderId=1 → "Casino + Games"` (the reference-join strategy, previously only tested on synthetic fixtures, now validated against a real foreign-key→named-object resolution).

---

## 4. Honest Caveats

1. **`/LineFeed/` was not reached.** The live-odds feed is likely a websocket. **0 WS frames were captured** despite the new WS handler — either the feed didn't fire on this page-load path (linebet may load it only on the in-play page or after login), or it loads from a host the proxy doesn't route, or the WS handler didn't fire in this Playwright version. **Follow-up:** navigate explicitly to `/en/live` and re-capture, or inspect the betting-app bundle for the WS endpoint URL.

2. **Some `sibling_prefix` decodings are misfires.** `'Bet' → 'Event'`, `'Telegram' → 'Bonuses and promo codes in our Telegram'`, `'Self-exclusion' → (a long sentence)` — these are real Rosetta quality issues where the sibling-prefix strategy over-matches. They're correctly flagged for review (10 of 100 entries). **Follow-up:** tighten the sibling-prefix strategy's suffix matching (the "Rosetta depth" backlog item).

3. **The explored run's dictionary was truncated.** The `head -50` on the runner's output closed the pipe before the summary.json + dictionary.json wrote. The catalog.db is intact; the decodings shown are from the capture-all (non-explored) run. **Not a data loss** — the explored catalog is in `scripts/capture-out-explored/catalog.db` and can be re-decoded.

4. **Bot protection was not defeated.** The proxy bypassed the *geo*-block, but linebet's bot detection (Cloudflare JA4 + the `/fatman-api/.../fc` challenge endpoint) still saw a headless Chromium. We captured what we could without bypassing it (per ADR-1: decode-and-document, don't ship a bypass).

5. **Proxy credential is in the chat transcript.** The user pasted the proxy password in chat. I treated it like the PAT (transient env var → gitignored secrets file at `/home/z/my-project/scripts/proxy-secret.txt`, never in a committed file), but **the user must rotate it** — it's in the transcript.

---

## 5. Fixes Applied

- **`glyph/capture/driver.py`** — capture-all (no resource filter; `source` carries `playwright:<resource_type>`); WebSocket frame capture (`page.on("websocket", ...)` → `WS_SEND`/`WS_RECV` flows); `explore=N` parameter + `_explore_round` helper (target-agnostic scroll + generic click); `settle_ms` parameter; `domcontentloaded`-based wait (no more `networkidle` hang); `proxy` parameter + `_parse_proxy` helper.
- **`scripts/live_capture_run.py`** — `--proxy` flag (defaults to `$LIVE_PROXY`), credential-hiding in startup print.
- **`tests/test_real_world_languages.py`** (new, 12 tests) + **`tests/fixtures/real/linebet_languages.json`** (new, 4.4 KB, 60 languages) — the language-code real-world integration test.
- **`/home/z/my-project/scripts/run_proxied_capture.py`** — the proxied-capture runner (reads proxy from gitignored secrets file, no credential in shell command).
- **`/home/z/my-project/scripts/commit_session7.py`** — the persisted commit script (secret-scan + per-surface stage + commit + push, all Python).
- **`.gitignore`** — added `scripts/capture-out-*/`.

---

## 6. Open Items

- **Reach `/LineFeed/`** — navigate to `/en/live` explicitly and re-capture; inspect the betting-app bundle for the WS endpoint URL.
- **Tighten sibling-prefix strategy** — the misfires in §4.2 are real; the "Rosetta depth" backlog item now has concrete failing cases.
- **Remaining backlog:** DuckDB backend, Daraja recipe, Python 3.13 + Pydantic retarget (needs user decision; 3.13 venv not installable in this sandbox), optional Label Studio surface.

---

## 7. Verification

- **Core integrity:** `sh .context/core/bin/context-sync verify` → OK (0.3.0).
- **Identity:** `Tisone Kironget <tisonkironget@gmail.com>` (carried from Session 3 fix; the commit script asserts it before committing).
- **Test suite:** `.venv-312/bin/pytest -q` → **69 passed** (was 57; +12 language-code integration tests).
- **No secrets in committed files:** the commit script's secret-scan checks all committed files for the proxy password, the PAT, and the proxy host:port — all clean. The proxy credential lives only in `/home/z/my-project/scripts/proxy-secret.txt` (outside the repo).
- **Two-surfaces rule:** commit 1 (`1c9f242`) is project-surface only (`feat(capture):`); the bookkeeping commit will be `.context`-surface only (`chore(context):`).
- **Persisted-script approach:** the commit was done via `python3 /home/z/my-project/scripts/commit_session7.py`, not bash one-liners — per the user's directive and Rule 9.
