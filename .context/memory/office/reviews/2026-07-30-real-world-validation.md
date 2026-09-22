# Real-World Validation — Session 6 Report

> Session 6 — the user said "tackle backlog," then directed a live capture against a real target when I offered to wait for a HAR. Set up the venv, installed the live extra + chromium, drove headless Playwright at linebet.com, and ran the full pipeline end-to-end. Rosetta decoded 104 opaque codes against the real capture, 99 at high confidence — locked in as a repeatable integration test. Three backlog items closed.

---

## 1. Executive Summary

Session 6 delivered the **real-world validation** the user has been asking for since Session 4 (`user/preferences.md` → Testing: *"Tests can pass 100% because they were 'conditioned to pass that way' while the software still fails in the real world"*). The 45 unit tests over hand-authored fixtures proved internal consistency; this session proved the pipeline works against a real, messy, third-party target.

**What ran:** `playwright install chromium` succeeded in the Z.ai sandbox → `glyph.capture.driver.capture_url` drove headless chromium at `https://linebet.com/en/line/basketball` → captured 20 flows across 17 endpoints with response bodies + a DOM snapshot → `infer_all` flagged 115 enum candidates → `build_dictionary` (Rosetta) decoded **104 entries, 99 high-confidence, 5 needing review**.

**The decodings are real and correct.** Spot-checks against what a human would read off the linebet contacts page:

| Code field | Code value | Rosetta decoded | Human-readable label |
|---|---|---|---|
| `networks[].templateType` | 17 | "X" | ✓ (Twitter/X icon) |
| `networks[].templateType` | 14 | "Facebook" | ✓ |
| `networks[].templateType` | 13 | "Instagram" | ✓ |
| `networks[].templateType` | 9 | "Telegram" | ✓ |
| `emails[].templateType` | 3 | "Security department" | ✓ |
| `emails[].templateType` | 6 | "Queries and suggestions" | ✓ |
| `phones[].templateType` | 1 | "CUSTOMER SUPPORT" | ✓ |
| `networks[].templateCode` | 'x' | "X" | ✓ (cross-validates the int code) |
| `emails[].templateCode` | 'security_service' | "Security department" | ✓ |

**Locked in as a repeatable test:** `tests/test_real_world.py` (12 integration tests, kept separate from the unit suite per the backlog item's ask) runs the full pipeline against `tests/fixtures/real/linebet_contacts.json` — a real payload extracted from the live capture, with actual contact values (phone numbers, email addresses, social URLs) redacted to placeholders and the code→label structure preserved verbatim. **57 tests pass total** (was 45; +12 real-world).

**Three backlog items closed:** Phase-0 proof, Live-capture end-to-end run, Real-world validation.

---

## 2. Discovery Phase

### What the user asked for
- "Now we tackle backlog in this session" — work the open backlog items.
- "Which kind of target do you want?" — clarifying which target for the real-world-validation items.
- "Captured XHR file" — the user uploaded `betting.xhr` (a HAR from linebet.com).
- "Actually you can initiate .venv and install dependencies and run live capture" — the user pushed back on my assumption that live capture wasn't possible in the sandbox.

### What I found in the uploaded HAR
The uploaded `betting.xhr` was a real HAR from `linebet.com/en/line/basketball` (116 entries, all GET to `v3.traincdn.com`) — but with **0 response bodies** and **0 DOM snapshots**. It captured that the requests happened but not the data Rosetta needs to decode. (Chrome DevTools "Save all as HAR" sometimes strips response content depending on the export option.)

### The pivot to live capture
The user's "actually you can initiate .venv and run live capture" was the right call. I'd assumed `playwright install chromium` would fail in the sandbox — it didn't. The `[dev]` extra I installed earlier already pulled in `[live,schema,analytics]` (mitmproxy 12.2.3, playwright 1.61.0, genson 1.4.0, duckdb 1.5.5). The only missing piece was the chromium binary, which installed cleanly. Headless chromium launches and renders.

---

## 3. Baseline Health

- **Core integrity:** `sh .context/core/bin/context-sync verify` → OK (0.3.0).
- **Identity:** confirmed `Tisone Kironget <tisonkironget@gmail.com>` still set from the Session 3 correction.
- **Test suite before:** 45 pass (Python 3.12 venv, `.venv-312`).
- **Test suite after:** 57 pass (+12 real-world integration tests).
- **Python versions available:** 3.9 (system, per Session 4), 3.12.13, 3.13.5. **3.13 venv is NOT installable** in this sandbox (`python3.13-venv` package missing) — recorded in `system/environments.md`. Tests run on 3.12.

---

## 4. The Live Capture Run

### Setup
- `.venv-312` (Python 3.12.13) with `glyph-re[dev]` installed (includes `[live,schema,analytics]`).
- `playwright install chromium` → succeeded (chromium 149.0.7827.55, headless).
- Reusable script at `scripts/live_capture_run.py` — drives `glyph.capture.driver.capture_url`, runs `infer_all` + `build_dictionary`, dumps artifacts.

### What was captured
- **20 flows across 17 endpoints** (vs 116 in the manual HAR — the headless browser hit a partial block/consent interstitial, referer `/en/block`, so the capture is shallow).
- **1 DOM page** (the rendered HTML at capture time).
- **7 DOM labels harvested** (the SPA hadn't fully rendered; the heavy DOM-strategy contribution didn't materialize — see §6 caveat).
- **3 endpoints had JSON schemas inferred** (the rest were SVG/binary/non-JSON).
- **115 enum candidates flagged** — `templateType`, `templateCode`, `placement`, `iconId`, `networks`, `emails`, etc.

### What Rosetta decoded
- **181 raw candidates** (sibling + dom_attr + reference strategies).
- **104 dictionary entries** after grouping + scoring + dedup.
- **99 high-confidence**, 5 needing review.
- **The sibling_generic strategy carried it** — code field (`templateType`/`templateCode`) sitting next to a label field (`title`) in the same JSON object, exactly as RESEARCH.md §5 predicted for the "sibling pairing" case.

### Endpoints that produced decodings
The decodings came from `GET /bff-api/config/group/get?groups=b.core,d.core` — linebet's contacts/config endpoint, which returns the social networks, phone numbers, and email addresses with their `templateType` (int code) + `templateCode` (string code) + `title` (human label) as sibling fields. The betting-events API (`/fatman-api/{hash}/event.json`) was captured but only twice and didn't yield decodings in this shallow run.

---

## 5. Locking It In — The Integration Test

Per the backlog item's ask ("Add these as integration tests kept separate from the unit suite"), I extracted a minimal fixture and wrote a dedicated test file:

- **`tests/fixtures/real/linebet_contacts.json`** (7.8 KB) — the `networks[]` (12 items), `phones[]` (5), `emails[]` (12) arrays from the captured config payload. Actual contact values redacted to placeholders (`REDACTED@example.com`, `+000-0000`, `REDACTED_SOCIAL_URL`, `REDACTED_HANDLE`); the code→label structure (`templateType`/`templateCode`/`title`/`labelKey`) preserved verbatim. No secrets — verified by scanning for bearer tokens, cookies, session IDs, API keys (0 found).

- **`tests/test_real_world.py`** (12 tests) — loads the fixture as a single flow into a fresh in-memory Catalog, runs `infer_all` + `build_dictionary`, asserts the known decodings:
  - `test_networks_templateType_decodes_to_brand_name` (parametrized: 17→X, 14→Facebook, 13→Instagram, 9→Telegram) — 4 tests
  - `test_networks_templateCode_decodes_to_brand_name` (parametrized: x→X, facebook→Facebook, instagram→Instagram, telegram→Telegram) — 4 tests, cross-validates int vs string codes
  - `test_emails_templateType_decodes_to_department` (parametrized: 3→Security department, 6→Queries and suggestions) — 2 tests
  - `test_real_dictionary_has_nontrivial_size` — ≥20 entries
  - `test_real_decodings_are_high_confidence` — ≥8 high-confidence templateType decodings

All 12 pass. If any of these break, the pipeline regressed on **real-world data**, not just synthetic fixtures.

---

## 6. Honest Caveats (per `user/preferences.md`)

I will not report "57 tests pass" as evidence the software works in the real world without naming what the tests do and don't cover:

1. **The capture was shallow.** 20 flows / 7 DOM labels — the headless browser hit a partial block interstitial (`/en/block` referer). A full betting-line capture (events, markets, odds with their opaque codes) needs a non-blocked session or interaction (scroll, click-to-expand markets) to trigger the events/odds API calls. The `templateType` decodings that landed are from the **contacts/config** endpoint, not the betting markets themselves.

2. **The DOM-attribute strategy (Rosetta's thesis centerpiece) barely fired.** The 7 harvested DOM labels weren't enough for meaningful DOM↔API correlation. The sibling strategy (code next to label in the same JSON object) carried the decoding — that's real and correct, but it's the "easy half" of Rosetta. The DOM-pairing half (the part that's genuinely novel per RESEARCH-DEEP-DIVE §4) was exercised but contributed little because the SPA hadn't fully rendered when `page.content()` was called. **Deeper capture + DOM-strategy validation is the natural follow-up.**

3. **The 104 decodings are real but narrow.** They're all `templateType`/`templateCode` → brand/department labels from one config endpoint. The harder decoding case — betting-specific opaque codes (event type ids, market type ids, odd result codes) that a human analyst would spend hours guessing — wasn't reached in this shallow capture.

4. **The reference-join strategy produced candidates but I didn't spot-check them.** The 104 entries include reference-join decodings (foreign-key-like `*_id` fields resolving to named objects elsewhere); the integration test only asserts the sibling decodings, which are the ones I could hand-verify against the rendered page.

5. **Bot protection was not defeated.** The headless browser got a partial block (not a full Cloudflare wall, but a `/en/block` interstitial). Per ADR-1, I decoded-and-documented what I could reach; I did not ship a bypass. A deeper capture would need either a non-headless session, a residential IP, or an authorized cookie/consent state — all out of scope for this session.

---

## 7. Fixes Applied

- **`scripts/live_capture_run.py`** (new) — reusable live-capture + full-pipeline runner. Drives `glyph.capture.driver.capture_url`, runs `infer_all` + `build_dictionary`, dumps `summary.json` + `dictionary.json` + `catalog.db` to a chosen output dir. Parametrized on URL (defaults to linebet.com/en/line/basketball).

- **`scripts/extract_fixture.py`** (new) — extracts the `networks[]`/`phones[]`/`emails[]` arrays from a captured catalog.db, redacts contact values, writes the minimal real-world fixture. Used once to produce `tests/fixtures/real/linebet_contacts.json`; persisted as a script (Rule 9) so it's recoverable if the fixture needs regenerating.

- **`tests/test_real_world.py`** (new, 12 tests) — the real-world integration test. Separate from the unit suite per the backlog item's ask. Asserts the known `templateType`/`templateCode` → label decodings against the real fixture.

- **`tests/fixtures/real/linebet_contacts.json`** (new, 7.8 KB) — the real captured payload, contact values redacted, code→label structure preserved.

- **`.gitignore`** — added `scripts/capture-out/`, `*.db`, `.venv-*/` so scratch capture artifacts and venvs don't get committed.

- **`memory/tasks/backlog.md`** — checked off 3 items (Phase-0 proof, Live-capture E2E, Real-world validation) with the session/commit references.

---

## 8. Open Items

The remaining open backlog items (unchanged by this session):
- **DuckDB catalog backend** — not started.
- **Rosetta depth: Splink + positional/value-inferred** — not started. (This session's caveat #2 makes this more relevant — the DOM strategy needs strengthening.)
- **Daraja callback verification recipe** — not started.
- **Retarget to Python 3.13 + evaluate Pydantic** — not started; needs user decision (3.13 venv isn't installable in this sandbox — only 3.12 tested here).
- **Optional: Label Studio review surface** — low priority.

**New follow-up from this session (not yet in backlog):**
- Deeper live capture against linebet.com (non-blocked session or page interaction) to reach the betting-events API and validate the DOM-attribute strategy with a fully-rendered SPA.

---

## 9. Recommended Next Steps

1. **Deeper capture** — re-run with page interaction (scroll the line, click a match to expand markets, wait for `networkidle` after each interaction) to trigger the betting-events/odds API calls. That's where the hard decoding work (event type ids, market type ids) lives.
2. **Strengthen the DOM strategy** — harvest labels after explicit `wait_for_selector` on rendered content, or capture multiple DOM snapshots over time. This is the "Rosetta depth" backlog item made concrete by this session's caveat #2.
3. **DuckDB backend** — the store interface is ready; the 115 enum candidates + 104 dictionary entries from this run are a concrete dataset to test drift analytics against.
4. **Daraja recipe** — still the highest-value Kenya-priority deliverable; self-contained, no live target needed.

---

## 10. Verification

- **Core integrity:** `sh .context/core/bin/context-sync verify` → OK (0.3.0), 2026-07-30.
- **Identity:** `git config user.email` → `tisonkironget@gmail.com` (carried from Session 3 fix).
- **Test suite:** `.venv-312/bin/pytest -q` → **57 passed** (45 unit + 12 real-world integration).
- **No secrets in committed files:** scanned `scripts/live_capture_run.py`, `scripts/extract_fixture.py`, `tests/test_real_world.py`, `tests/fixtures/real/linebet_contacts.json`, `.gitignore` for bearer tokens / cookies / session IDs / API keys / 40+ char hex strings → 0 found. The captured `catalog.db` (with capture-session-specific URLs and the `x-fc` challenge header) is gitignored under `scripts/capture-out/` and `*.db` — not committed.
- **Two-surfaces rule:** project surface (`scripts/`, `tests/`, `.gitignore`) uses `feat:`/`test:`/`chore:`; `.context` surface (backlog, current, this report) uses `chore(context):`/`docs(review):`. Never mixed.
- **Append-only integrity:** `backlog.md` diff reviewed — only `+` lines for the checked-off items (the `[ ]` → `[x]` is an in-place edit per the file's own rule "When an item is done, check it off and note the session/commit — don't remove the line").
