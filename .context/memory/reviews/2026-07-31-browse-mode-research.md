# Research note — Browse Mode (`glyph run live --browse <target>`) (Session 19)

- **Date:** 2026-07-31
- **Agent:** Super Z / unknown (cloud sandbox, Python 3.12.13)
- **Purpose:** Research how to implement `--browse` mode for `glyph run live <target>`.
  Same as `glyph run live` today, BUT the browser is VISIBLE and the USER drives it
  (logs in, submits forms, makes payments, deposits, withdraws, sends money, etc.) while
  live capture continues in the background. Goal: capture endpoints the current
  auto-explore path misses — auth flows, payment flows, login, deposits, withdrawals,
  transfers, anything gated behind user-driven multi-step journeys.
- **Feeds:** **ADR-13 (proposed)** in `plans/decisions.md`. Build session will follow.

---

## 1. Problem statement

Today, `glyph run live <url>` (`glyph/cli/run.py::run_live`):

1. Opens the live TUI dashboard (`glyph.tui.app.DashboardScreen`), which spawns a
   worker thread that calls `glyph.capture.driver.capture_url`.
2. `capture_url` launches Chromium **headless**, calls `page.goto(url)`, waits for the
   page to settle, then runs N target-agnostic `_explore_round` passes (scroll 3x,
   pseudo-random generic clicks on `a, button, [role=button], [class*='item']` etc.).
3. Every response is recorded via `page.on("response", on_response)` → `Flow(...)` →
   `catalog.add_flow(flow)`. WebSocket frames via `page.on("websocket", ...)`. DOM
   snapshot via `_snapshot(page)` → `page_observations`.
4. When the explore rounds finish, capture ends; analysis runs.

**What this captures well:** anything reachable by *generic* click/scroll on the
landing page — public catalogue APIs, lazy-loaded lists, live-odds streams, SPAs whose
data loads on initial render.

**What this CANNOT capture** (the user's pain):

- **Auth/login flows** — no form filling, no credential submission, no OTP entry.
  The page never gets past the login wall, so every authenticated endpoint stays
  invisible.
- **Payment / deposit / withdrawal flows** — require entering an amount, selecting a
  provider, confirming via PIN/OTP, sometimes navigating modals/wizards. Generic
  clicks never trigger these in a useful sequence.
- **Send/transfer flows** — multi-step forms (recipient → amount → review → confirm).
- **Account-state-specific endpoints** — `/api/wallet/balance`, `/api/transactions`,
  `/api/profile`, anything that returns 401 unauthenticated but loads of value once
  the user is logged in.
- **KYC / verification flows** — modal wizards, document upload, step-by-step forms.
- **Hidden / modal flows** — anything behind "click here to deposit" buttons that
  generic clicks won't reliably aim at.

The user's framing: *"A browser pops up, the user interacts with it while the live
capture is continuing — same as `glyph run live` but with real browser and user
actually navigates."* So the *capture mechanism* doesn't need to change; the
*driving* changes from auto-explore to human-driven.

---

## 2. Techniques evaluated

### Technique A — Playwright (headless=False, user-driven) ✅ RECOMMENDED for v1

The current `capture_url` already uses Playwright's hooks. Those hooks fire on
**every** response / WS frame the browser sees — they don't care who initiated the
navigation. So the *only* essential change is `launch_kwargs["headless"] = False`
plus a "wait for the user to close the browser" loop instead of the explore rounds.

What's already there:

- `page.on("response", on_response)` — captures every HTTP response (any resource
  type: document, script, xhr, fetch, websocket handshake, image, font…). The
  response body is **decrypted plaintext** because Playwright reads it AFTER TLS
  termination inside the browser.
- `page.on("websocket", on_websocket)` — registers `framesent` / `framereceived`
  handlers that record WS payloads in both directions.
- `_snapshot(page)` — captures the rendered HTML + plain text + harvested labels
  into `page_observations` (the DOM input Rosetta needs).
- `catalog.add_flow(flow)` is called **the moment each response is seen** (Phase 2
  of ADR-9) — so a crash never loses captured data and the live TUI can stream.

What browse mode adds:

| Hook / change | Why |
|---|---|
| `launch_kwargs["headless"] = False` | Browser visible to the user. |
| Skip `_explore_round` (or make it opt-in via `--explore` even in browse) | The user is driving; auto-clicks would fight them. |
| `context.on("page", ...)` | When the user opens a new tab (Ctrl+click, `target=_blank`, "open in new tab"), register the same response/WS/snapshot handlers on the new page. **Critical** — betting/payments sites love new tabs. |
| `page.on("framenavigated", ...)` | Refresh the DOM snapshot when the user navigates (link click, form submit, address-bar nav within the page). Keeps `page_observations` current for Rosetta. |
| `page.on("request", ...)` (NEW) | Today only responses are recorded. Adding the request side captures requests whose responses never arrive (cancelled, preflight-rejected, beacon fire-and-forget). `response.request` already gives you the matching request for recorded responses, so this is purely additive for the gap. |
| `browser.on("disconnected", ...)` (or `context.on("close", ...)`) | The exit signal — user closes the browser, capture ends, `capture_status = "done"`, analysis runs. |
| `launch_persistent_context(user_data_dir=..., headless=False)` | Persistent cookies/localStorage IndexedDB across captures. Login survives — the user logs in once, all future `glyph run live --browse <host>` sessions start already-authenticated. Per-host profile dir. |
| Periodic `context.cookies()` snapshot (every ~5s + on disconnect) | Cookie reads via `document.cookie` are invisible to the response hook. Snapshotting lets `glyph sensitive` flag auth tokens in cookies later. v1: stash in `page_observations` or a meta blob; v2: dedicated `cookies` table. |

**Strengths**

- **Minimum disruption.** ~50–100 LOC across `driver.py`, `_shared.py`, `run.py`,
  `capture.py`. No new dependencies — `[live]` already pulls Playwright.
- **Decrypted bodies for free.** Playwright sees responses AFTER TLS termination;
  `response.text()` returns plaintext. mitmproxy has to MITM TLS (cert install +
  pinning breakage).
- **DOM stays.** Rosetta's DOM-strategy (`data-status="3"` ↔ "Shipped" sibling
  labels) keeps working — `_snapshot(page)` already does this.
- **Multi-tab support.** New tabs the user opens are captured too.
- **WebSocket payloads both directions** (already wired).
- **Backward compatible.** `--browse` is opt-in; existing `glyph run live` behavior
  is unchanged.
- **Cookie/session persistence** via `launch_persistent_context` — log in once, all
  future runs start already-authed.

**Limitations (be honest)**

- **Browser-only.** Traffic from a companion mobile app, desktop client, or another
  browser is NOT captured. Out of scope for `--browse`; covered by `glyph capture
  har` (any tool's HAR) or the future pcap→HTTP adapter (ADR-6).
- **Service-worker / beacon / prefetch traffic** MIGHT slip past
  `page.on("response")` in rare cases. Mitigation: also hook `page.on("request")`
  (records the request side; if the response hook never fires, we still have the
  request URL + headers + body).
- **`document.cookie` reads** are invisible to either hook. Mitigation: periodic
  `context.cookies()` snapshot.
- **HTTP/3 (QUIC).** When `--proxy` is set, Chromium auto-disables QUIC (proxy can't
  speak QUIC) — non-issue. When NO proxy is set, Chromium MAY use QUIC for some
  hosts; Playwright's response hook DOES see it (browser-layer interception), so
  this is also fine. Documented for completeness.
- **Browser extensions.** Playwright launches a fresh Chromium profile by default;
  user-installed extensions (ad blockers, password managers) are NOT loaded. The
  `launch_persistent_context` + `--load-extension` flag can carry a curated set
  (advanced; defer to v2).
- **Address-bar typing.** Playwright owns the address bar; if the user types a new
  URL into the Chromium address bar, the navigation DOES fire `framenavigated` (and
  the response hook captures the new page) — so this works. But typing in the
  terminal (where `glyph` was launched) is consumed by the terminal, not the
  browser.

### Technique B — mitmproxy (system-wide proxy, no DOM) ❌ for v1

The repo already has `glyph/capture/mitm.py` (`GlyphAddon` writes every mitmproxy
flow into the catalog). To use for browse mode: start `mitmdump -s
glyph/capture/mitm.py` on a port, install mitmproxy's CA cert in the user's
browser, configure the browser to use the proxy.

**Strengths**

- Captures EVERY HTTP/HTTPS flow the browser makes — service workers, beacons,
  prefetch, OCSP, alt-svc, the lot.
- Works with ANY browser (Chrome, Firefox, Edge, Safari) — the user keeps their
  daily browser with saved logins, extensions, bookmarks.
- Full request side too (Playwright's `on_response` gives you both via
  `response.request`, but mitmproxy is more thorough on the wire).
- Solid WebSocket support (dedicated WebSocket flow type).

**Limitations**

- **TLS interception friction.** Requires installing mitmproxy's CA cert in the
  browser's trust store (or system trust store). Per-user, per-machine. Not
  one-command.
- **Certificate pinning.** Modern apps (especially mobile, but some web contexts
  with service-worker pinning too) reject mitmproxy's CA. Less of an issue for
  pure-browser traffic; near-universal for native apps.
- **No DOM access.** Rosetta's DOM-strategy (sibling labels, `data-*` attrs,
  rendered text near codes) is broken. Would need to pair mitmproxy with a
  separate DOM capture (a Playwright instance that just snapshots the page, or
  a browser extension). This is the killer for `--browse` mode.
- **HTTP/3 (QUIC) not supported** by mitmproxy (issue #7186). For QUIC, the
  browser must be told `--disable-quic` or traffic bypasses the proxy.
- **Manual setup.** User must configure the browser's proxy settings + install the
  cert. Defeats the "one command" goal.
- **`source` field** would be `"mitm"` (vs `"playwright:<type>"`) — catalog can
  tell the two apart, but mixing them on one capture is messy.

### Technique C — Hybrid (Playwright visible + mitmproxy upstream) 🟡 OPTIONAL future

Launch Playwright Chromium (visible, headless=False) with `proxy =
"http://localhost:8080"` pointing at a local `mitmdump -s
glyph/capture/mitm.py`. Both paths write into the same catalog; tag with
`source = "mitm"` vs `source = "playwright:<type>"`; dedupe by
(method, url, status, timestamp-window) if both see the same flow.

**Strengths**

- Maximum coverage — Playwright captures DOM + WS frames + decrypted bodies;
  mitmproxy captures the wire-level view (catches anything Playwright misses).
- Cross-validation: if mitmproxy sees a request Playwright's hook didn't fire on,
  that's a signal worth flagging.

**Limitations**

- Complexity: two concurrent capture processes, deduplication logic.
- mitmproxy CA must be trusted by Chromium — Playwright supports
  `ignore_https_errors=True` or cert injection via launch arg, but it's extra
  setup.
- Cookie duplication (Playwright context cookies + mitmproxy sees them in
  headers).
- Doubles capture latency per flow (mitmproxy intercepts, then Playwright sees
  the response).

**Verdict:** defer until a real target shows Playwright's coverage is
insufficient. ADR-6 already says "Glyph captures at the HTTP/application layer" —
Playwright at headless=False is the canonical implementation of that layer. Build
Technique A first; revisit Technique C if a concrete gap appears.

### Technique D — other techniques considered and rejected

- **CDP directly (Chrome DevTools Protocol).** Playwright already wraps CDP; its
  `page.on("response")` IS the CDP `Network.responseReceived` event. Using CDP
  directly would be more code for no benefit. Skip.
- **Selenium + BrowserMob Proxy.** Deprecated; Selenium 4 has its own CDP
  integration but is heavier than Playwright. No advantage. Skip.
- **Browser extension that records HAR.** Would require the user to install an
  extension, then export the HAR. This is exactly what `glyph run har` already
  supports — defeats the "live" goal. Skip.
- **Chrome DevTools "Recorder" panel.** Exports JSON / Puppeteer scripts; offline
  playback, not live capture. Skip.
- **Frida + on-device.** Out of scope for browser targets; relevant for native
  mobile apps (covered by ADR-6 + ADR-7).
- **SSLKEYLOGFILE + Wireshark.** Packet-level, explicitly out of scope per ADR-6.

---

## 3. Recommendation: Technique A (Playwright visible) for v1

### Why Playwright wins for `--browse`

1. **Already there.** The codebase uses Playwright; the response/websocket hooks
   are already wired; the catalog writes are already incremental (ADR-9 Phase 2).
2. **DOM access.** Rosetta's DOM-strategy is the project's centerpiece
   (RESEARCH.md §4). mitmproxy alone kills this; Playwright keeps it.
3. **Decrypted bodies.** Playwright sees responses AFTER TLS termination —
   `response.text()` returns plaintext. mitmproxy has to MITM TLS (cert
   installation + pinning breakage).
4. **One command.** `glyph run live --browse <url>` launches everything; no
   manual proxy configuration or cert installation.
5. **Cookie/session persistence.** `launch_persistent_context(user_data_dir=...)`
   lets the user's login survive across captures — important for revisiting
   auth-protected targets.
6. **Consistent with ADR-6** (HTTP/application layer) and **ADR-9** (TUI as
   presentation layer; the live dashboard stays the post-capture surface).

### What Playwright DOESN'T capture (be honest in the docs)

- Non-browser traffic (mobile companion apps, desktop clients) — out of scope for
  `--browse`; covered by `glyph capture har` (HAR from any tool) or the future
  pcap→HTTP adapter (ADR-6).
- Some service-worker / beacon traffic MAY slip past `page.on("response")`.
  Mitigation: also hook `page.on("request")`.
- `document.cookie` reads — invisible. Mitigation: periodic `context.cookies()`
  snapshot.
- HTTP/3 QUIC — handled (Chromium disables QUIC through a proxy; Playwright's
  response hook sees it when no proxy).

---

## 4. Proposed implementation (kickoff for the build session)

### ADR-13 (proposed — see `plans/decisions.md`)

**Browse Mode = Playwright visible, user-driven, persistent context.**

- New `--browse` flag on `glyph run live` and `glyph capture live`.
- `capture_url` gains `browse: bool = False` and `user_data_dir: Optional[str] = None`
  params.
- When `browse=True`:
  - `launch_kwargs["headless"] = False`.
  - Use `launch_persistent_context(user_data_dir, headless=False, ...)` when
    `user_data_dir` is set; else `launch(headless=False) + new_context()`.
  - Skip `_explore_round`.
  - Hook `context.on("page", ...)` for new tabs the user opens.
  - Hook `page.on("framenavigated", ...)` to refresh the DOM snapshot on nav.
  - Hook `page.on("request", ...)` to capture the request side (additive).
  - Block on `browser.on("disconnected", ...)` → set `capture_status = "done"`.
  - Default `user_data_dir = ~/.glyph/profiles/<host>/` (override via
    `GLYPH_PROFILE_DIR` env or `--profile <dir>` flag; `--incognito` uses a fresh
    ephemeral context).

### Code change plan

| File | Change |
|------|--------|
| `glyph/capture/driver.py` | Add `browse`, `user_data_dir` params to `capture_url`; switch to `launch_persistent_context` when `user_data_dir` set; `headless=False` when `browse`; register `context.on("page")`, `page.on("framenavigated")`, `page.on("request")`; block on `browser.on("disconnected")`; skip `_explore_round` when browse. Periodic `context.cookies()` snapshot (every ~5s + on disconnect). |
| `glyph/cli/_shared.py` | Add `--browse`, `--profile <dir>`, `--incognito` to `with_live()`; thread through `live_kwargs()`. |
| `glyph/cli/run.py` | In `run_live()`: when `args.browse`, do NOT take over the screen with the dashboard during capture (user needs the browser visible). Print a one-line "Browser open — navigate, log in, do your flows. Close the browser when done." to stderr; after browser-close, run `_gather` + `_render`, THEN optionally open the dashboard as a post-capture view (or print summary). |
| `glyph/cli/capture.py` | Same `--browse` plumbing for `glyph capture live --browse`. |
| `glyph/tui/app.py` | Home screen: add a "Browse mode" toggle (key `b`?) on the URL box; pass `browse=True` to the capture kwargs. (Optional v1 — defer if it complicates the dashboard worker model.) |
| `tests/test_capture_live.py` | Mock Playwright; assert `browse=True` → `launch(headless=False)` (or `launch_persistent_context(headless=False)`); assert `_explore_round` NOT called; assert `context.on("page")` registered; assert `browser.on("disconnected")` is the wait condition. |
| `README.md` | Document `--browse` in the live-capture section + the `~/.glyph/profiles/<host>/` persistence behavior. |

### Open questions for the user (call out, don't decide alone)

1. **TUI in browse mode.** Three options:
   - (a) Browser-only during capture + dashboard opens AFTER browser close
     (post-capture exploration view). Simplest; recommended for v1.
   - (b) Split-pane (browser + Textual dashboard side-by-side). Nicest UX; more
     work to manage two visible surfaces.
   - (c) Browser-only, no dashboard at all (just print summary). Matches
     `--no-tui` behavior; least useful.
2. **Profile persistence default.**
   - Persistent by default (`~/.glyph/profiles/<host>/`, login survives) + `--incognito`
     flag for fresh ephemeral context. **Recommended** — the whole point of browse
     mode is to log in once and capture authed flows.
   - OR incognito by default + `--profile <dir>` to opt into persistence.
3. **Closing signal.** Rely on browser-close only, OR also accept Ctrl+C in the
   terminal? Browser-close is cleaner (Chromium exits gracefully, profile flushes).
   Ctrl+C might leave the Chromium process running. Recommend: browser-close is
   the primary; Ctrl+C is a fallback that calls `browser.close()` then exits.
4. **Record the request side too?** (`page.on("request")`.) Recommend yes —
   captures requests whose responses never arrive (cancelled, preflight-rejected,
   beacon fire-and-forget). Additive; no downside.
5. **Periodic cookie snapshot.** v1: stash in `page_observations` or a meta blob.
   v2: dedicated `cookies` table (schema bump). Defer the table to v2; v1 just
   captures via `context.cookies()` and stores as a JSON blob in meta.

---

## 5. Sources / prior art

- Playwright `page.on("response")` captures every response —
  https://playwright.dev/python/docs/api/class-page#page-on
- Playwright `launch_persistent_context` for cookie/storage persistence —
  https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context
- Playwright multi-tab via `context.on("page")` —
  https://playwright.dev/python/docs/api/class-browsercontext#browser-context-on
- Playwright `page.on("request")` for the request side —
  https://playwright.dev/python/docs/api/class-page#page-on
- mitmproxy CA cert installation —
  https://docs.mitmproxy.org/stable/concepts-certificates/
- mitmproxy HTTP/3 (QUIC) NOT supported —
  https://github.com/mitmproxy/mitmproxy/issues/7186
- Existing project ADRs referenced: ADR-2 (architecture), ADR-3 (proxy-neutral),
  ADR-6 (HTTP/application layer), ADR-9 (TUI as presentation), ADR-12 (multi-target).
  See `.context/memory/plans/decisions.md`.

---

## 6. Honest self-check

- The recommendation (Technique A) is the path of least resistance, AND it's the
  right answer — not just the easy one. The codebase already commits to Playwright
  (ADR-6, ADR-9); the DOM access is non-negotiable for Rosetta; mitmproxy's
  cert-install friction is a real UX cost.
- The "what Playwright doesn't capture" list is honest. The mitigations are real
  (`page.on("request")` for the gap; `context.cookies()` for cookie reads; QUIC
  handled by Chromium's proxy behavior).
- This research does NOT implement the feature — it grounds ADR-13 (proposed) so
  the build session can move fast. The build session should: read this note, read
  ADR-13, implement per the code change plan, write tests, verify on a real
  auth-protected target (the user's SIM/betting account flow is the obvious
  end-to-end proof), then mark ADR-13 accepted.
- Open questions are explicitly flagged — the build session should not guess on
  those 5; ask the user.
