# Backlog (append-only)

Open items for future sessions. Append at the bottom; never delete or
reorder. When an item is done, check it off and note the session/commit —
don't remove the line.

<!-- TEMPLATE — copy below the last entry:
---
- [ ] **<short title>** (added YYYY-MM-DD by <agent>) — <enough context that
      a fresh agent can act on this without any chat history. Severity if known.>
-->

---
- [x] **Build MVP: pipeline stages 1–4 + drift monitor** (added 2026-07-29 by Claude Code;
      done 2026-07-30 by Claude Code, Session 4) — built as the `glyph-re` package: all 10
      stages (capture, catalog, schema, rosetta, fingerprint, auth, gating, codegen, drift,
      mobile) + CLI, 32 passing tests. See `reviews/2026-07-30-build-base-system.md`.
      Follow-ups tracked as new backlog items below (HITL UI, DuckDB, Splink, live-capture E2E).
- [x] **Phase-0 proof** (added 2026-07-29 by Claude Code; done 2026-07-30 by Super Z / glm-5.2,
      Session 6) — ran stages 1–4 live against linebet.com/en/line/basketball (headless chromium
      via `glyph.capture.driver`). Rosetta auto-derived a 104-entry dictionary, 99 high-confidence;
      spot-checks match hand-analysis (`templateType=14`→Facebook, `13`→Instagram, `9`→Telegram,
      `17`→X, `3`→Security department, `6`→Queries and suggestions). Locked in as a repeatable
      integration test (`tests/test_real_world.py`, 12 tests) against a real captured fixture
      (`tests/fixtures/real/linebet_contacts.json`). See Session 6 report.
- [x] **Decide repo/service split + catalog store** (added 2026-07-29 by Claude Code;
      done 2026-07-30 by Claude Code, ADR-2) — resolved: monorepo, stages as packages,
      catalog as a library, SQLite → DuckDB → Postgres. See `plans/decisions.md` ADR-2.
- [x] **README: proposed repo/package layout** (added 2026-07-29 by Claude Code;
      done 2026-07-30 by Claude Code, Session 4) — README now documents install, quickstart,
      and the pipeline/package table matching the built structure.

---
- [x] **HITL review UI for low-confidence dictionary rows** (added 2026-07-30 by Claude Code;
      done 2026-07-30 by Claude Code, Session 5) — built `glyph.review` + `glyph review`
      (interactive + `--auto-confirm` + single-entry `--id/--reject/--set` + `--stats`).
      Decisions persist (review_state column + migration) and survive Rosetta re-runs.
      Label Studio integration is now OPTIONAL, not required — see follow-up below.
      See `reviews/2026-07-30-hitl-review-workflow.md`.
- [ ] **DuckDB catalog backend** (added 2026-07-30 by Claude Code) — the store interface
      (`glyph.catalog.store.Catalog`) is ready for the ADR-2 promotion (SQLite → DuckDB when
      drift analytics matter). Not yet implemented. Medium.
- [ ] **Rosetta depth: Splink + positional/value-inferred correlation** (added 2026-07-30 by
      Claude Code) — current model is a hand-rolled noisy-OR over sibling/DOM/reference
      strategies. Add probabilistic matching (Splink, §4.6) and correlation for codes that
      neither sit next to a label nor appear in the DOM. Medium.
- [x] **Live-capture end-to-end run** (added 2026-07-30 by Claude Code; done 2026-07-30 by
      Super Z / glm-5.2, Session 6) — `playwright install chromium` succeeded in the Z.ai
      sandbox; `glyph.capture.driver.capture_url` ran live against linebet.com, captured
      20 flows / 17 endpoints with response bodies + DOM labels, and the full pipeline
      (catalog → schema → Rosetta) decoded 104 entries end-to-end. Reusable script at
      `scripts/live_capture_run.py`. Caveat: the headless browser hit a partial block/
      consent interstitial (`/en/block` referer), so the capture is shallow (20 flows, 7
      labels) — the full betting-line depth needs a non-blocked session or interaction
      (scroll, click-to-expand markets) to trigger the events/odds API calls. See Session 6.
- [ ] **Daraja callback verification recipe** (added 2026-07-30 by Claude Code) — concrete
      early deliverable (RESEARCH-DEEP-DIVE §3g): M-Pesa Daraja doesn't sign callbacks; ship
      a Glyph recipe that documents/verifies the gap. Low-Medium, Kenya-priority.
- [x] **Real-world validation of the pipeline (not synthetic)** (added 2026-07-30 by Claude
      Code; done 2026-07-30 by Super Z / glm-5.2, Session 6) — validated against a REAL live
      capture of linebet.com (not a hand-authored HAR). Rosetta reproduced hand-analysis:
      `templateType` ints → brand/department labels (Facebook, Instagram, Telegram, X,
      Security department, Queries and suggestions, Customer Support), all spot-checks
      correct, 99 of 104 entries high-confidence. Locked in as `tests/test_real_world.py`
      (12 integration tests, kept separate from the unit suite per the backlog item's ask)
      against `tests/fixtures/real/linebet_contacts.json` (real payload, contact values
      redacted, code→label structure preserved). Caveat: the capture was shallow (partial
      block interstitial) and the sibling strategy carried it — the DOM-attribute strategy
      (Rosetta's thesis centerpiece) was exercised but contributed little because the SPA
      hadn't fully rendered when the DOM snapshot was taken. Deeper capture + DOM-strategy
      validation is a follow-up. See Session 6 report.
- [ ] **Retarget to Python 3.13 + evaluate Pydantic models** (added 2026-07-30 by Claude
      Code) — user prefers 3.13 (Windows-stable) + Pydantic. Package was built 3.9/dataclasses
      as a stopgap. Decide with the user, then: bump `requires-python`, drop the `__future__`
      workarounds, and consider replacing `glyph.catalog.models` dataclasses with Pydantic
      (revisits ADR-2's zero-dependency base — Pydantic is a hard dep). Medium.
- [ ] **Optional: Label Studio review surface for teams** (added 2026-07-30 by Claude Code) —
      the terminal + scriptable `glyph review` workflow (Session 5) covers single-analyst use.
      A Label Studio export/import (RESEARCH-DEEP-DIVE §4.6) would give teams a GUI review
      surface. Not needed for solo use; only if a multi-analyst workflow is wanted. Low.
- [ ] **mitmproxy vs Playwright live head-to-head** (added 2026-07-31 by Claude Code) —
      compare endpoint/flow coverage of the mitmproxy addon vs the Playwright driver on the
      same target. BLOCKED locally: the sandbox classifier denies running `mitmdump` as a
      local proxy that upstreams to an authenticated external tunnel. Needs the user to allow
      `mitmdump` (Bash permission rule) or run it themselves and hand over the catalog.
      Grounded prediction (Session 9): Playwright wins for web/DOM targets (captures all
      resource types + the DOM Rosetta needs); mitmproxy's edge is mobile/native no-DOM
      clients — complementary, not competing. Low-Medium.
- [ ] **Verify WebSocket frame capture in the driver** (added 2026-07-31 by Claude Code) —
      `glyph.capture.driver` registers `framesent`/`framereceived` handlers (Session 7), but
      confirm it actually stores frame *payloads* (not just the handshake) end-to-end against
      a live WS target (e.g. live-odds streams). This is the one area mitmproxy would clearly
      capture more if the driver doesn't. Medium.
- [x] **Sensitive data / endpoint / risk flagging** (added+done 2026-07-31 by Claude Code,
      Session 10) — `glyph.sensitive` + `glyph sensitive` CLI: PII/secret/financial detection
      (kept, not redacted), path-based sensitive-endpoint classification, and passive risk
      indicators (secrets-in-URL, unauthenticated sensitive data, wildcard CORS, missing
      security headers, verbose errors, guessable-id IDOR). Passive only. RESEARCH.md §6j.
      Follow-up: optional redacted-EXPORT command (redaction is export-only, never at rest).
- [ ] **Extend the tracking-vendor list** (added 2026-07-31 by Claude Code, Session 10) —
      `glyph/sensitive/party.py` `_TRACKING_VENDORS` misses pixel/ad hosts seen live (tapad,
      snapchat `tr.`, eskimi, inmobi, decibelinsight) — they show as generic third-party
      instead of noise. Safe direction (shows more), but extend the set. Low.
- [ ] **guessable_object_id: skip static-asset paths** (added 2026-07-31 by Claude Code,
      Session 10) — fired on `collection.decibelinsight.net/i/{id}/{id}/di.js` (a static JS
      asset, not an API/object). In `glyph/sensitive/risk.py::_guessable_ids`, skip endpoints
      whose path ends in `.js/.css/.png/...` or is clearly a static asset. Low-Medium.
- [ ] **Related-domain (same-org) heuristic** (added 2026-07-31 by Claude Code, Session 10) —
      `flashscore.com`/`lsapp.eu`/`flashscore.ninja` are one org but different registrable
      domains, so reference-join won't cross them and party tags them third-party. A shared
      brand-label heuristic (e.g. `flashscore` appears in both) could recover them. Medium,
      false-positive risk — design carefully. Affects `rosetta` scoping + `sensitive/party`.
- [ ] **build_dictionary --fresh / clear stale entries** (added 2026-07-31 by Claude Code,
      Session 10) — `glyph.rosetta.build_dictionary` upserts but never removes rows no longer
      produced, so a re-decode after a logic change keeps stale decodings. Add a fresh/clear
      option (respect human-reviewed rows). Low-Medium.
- [ ] **Implement ADR-7: recursive bundle mining in `glyph.mobile`** (added 2026-07-31 by
      Claude Code, Session 13) — extend `glyph/mobile/apk.py` to detect a bundle (multiple
      `.apk` entries, a `manifest.json`, or an `Android/obb/` dir) and recurse ONE level: mine
      every inner APK (dex + native `.so` + resources) and scan OBB/asset entries for URLs/API
      paths. Keep the per-entry size cap; static string mining only (no bundletool/adb/install).
      See ADR-7 + `reviews/2026-07-31-capture-mobile-scope-research.md`. Medium.
- [ ] **Optional pcap→HTTP import adapter (ADR-6)** (added 2026-07-31 by Claude Code, Session 13)
      — only if a target needs packet-level capture: a thin importer that turns a decrypted pcap
      (tshark / PolarProxy + SSLKEYLOGFILE) into catalog `Flow`s, same interface as HAR ingest.
      Keep scapy/pyshark OUT of core deps (optional extra). Low — build on demand. See ADR-6.

---
- [ ] **SNI bug-host hunting: live carrier verification** (added 2026-07-31 by Super Z, Session 16)
      — the `glyph.snihunt` stage surfaces CANDIDATES by recon (reverse-IP, CT logs, CDN
      detection, zero-rating heuristics); it does not verify a candidate actually passes a
      specific carrier's DPI as zero-rated (that needs the user's SIM + a real tunnel test on
      the target network). Build an OPTIONAL recipe: given a candidate SNI, open a TLS tunnel
      through the carrier and measure whether bytes flow without data balance dropping. Out of
      scope for the core stage (per-target, on-device); track as a follow-up. Low-Medium. See
      ADR-10.
- [ ] **SNI hunt: enrich the zero-rating TLD/pattern set** (added 2026-07-31 by Super Z, Session 16)
      — `glyph/snihunt/zerorate.py::_ZERO_RATED_PATTERNS` ships the well-known global free
      surfaces (Facebook Free Basics, Wikipedia Zero, internet.org, Free Fire free-pack). The
      Kenya/East-Africa carrier free-pack domains (Safaricom/MTN/Airtel zero-rated hosts) are
      operator-specific and rotate; extend the set as the user reports live hits. Low. See ADR-10.
- [ ] **SNI hunt: second CT-log source failover** (added 2026-07-31 by Super Z, Session 16)
      — certspotter is the primary CT source (crt.sh is slow/timeout-prone in practice, kept as
      a fallback). If both are down, the stage degrades gracefully (local heuristics only). A
      third source (Google CT search, Censys subdomain API) would harden enumeration. Low. See ADR-10.

---
- [ ] **Port remaining InjectX decryptors into glyph.vpndec** (added 2026-07-31 by Super Z, Session 17)
      — HAT (HA Tunnel, scheme E1 AES-128-ECB), NPV (NapsternetV, C1 subtraction cipher), NSH
      (SocksHTTP, D1 AES-128-GCM+PBKDF2), VHD (G1 AES-128-CBC). The architecture is extensible
      (one module + one router entry each); the algorithms are in InjectX
      `backend/decrypt/{hat,npv,nsh,vhd}_decrypt.py`. Medium. See ADR-11.
- [ ] **Port HC v2.7+ (A5) and EHI v2 (B2) decryptors** (added 2026-07-31 by Super Z, Session 17)
      — the newer ChaCha20/Argon2 schemes. InjectX has them (`hc_v27_decrypt.py`,
      `ehi_v2_decrypt.py`); porting is straightforward but the algorithms are more involved
      (multi-layer ChaCha20 + RST AES-ECB + per-field JKL for A5; Argon2id + XXTEA +
      ChaCha20-Poly1305 for B2). Medium. See ADR-11.
- [ ] **snihunt: probe.py test coverage + 429 handling** (added 2026-07-31 by Super Z, Session 16
      carried to 17) — the active SNI probe (opt-in) has zero test coverage (needs mocked
      ssl.wrap_socket); "429-aware" is claimed in ADR-10 but get_json swallows 429 with no
      backoff/Retry-After. Low-Medium. See ADR-10.

---
## 2026-07-31 — Session 18 follow-ups (ADR-12 multi-target)

- **TUI target picker.** The dashboard (`glyph dashboard`) opens a fresh
  `Catalog` with no active target, so every tab shows ALL targets' rows
  mixed. Add a target picker (key `t`? a sidebar?) that calls
  `set_active_target(id)` and re-renders all tabs filtered to it. MVP
  workaround: `glyph target show <host>` for per-target counts.
- **`glyph --target <host>` global flag.** Scope `glyph sensitive`/`dict`/
  `flows`/`catalog`/`schema` to one target without passing `--target` per
  command (only `glyph sensitive` has it today). Implement as a top-level
  `--target` that sets the active target on the opened Catalog.
- **Guard `glyph target rm 0`.** Removing the unassigned target is allowed
  (deletes scratch rows), but `__init__` re-creates the id=0 row on next
  open. Document this, or guard it with a `--force` if users find it
  confusing.
- **`set_reachability` target scoping.** `set_reachability(endpoint_id, ...)`
  doesn't take a target filter — works because `endpoint_id` is already
  per-target under ADR-12, but worth a docstring note.

---
## 2026-07-31 — Session 19 follow-ups (Browse Mode research → ADR-13 proposed)

The build session implements ADR-13. Research + plan are done; these are the
concrete build items + open questions. See
`reviews/2026-07-31-browse-mode-research.md` and ADR-13 in `plans/decisions.md`.

- [ ] **Implement ADR-13: `--browse` flag on `glyph run live` + `glyph capture live`**
      (added 2026-07-31 by Super Z, Session 19) — `capture_url` gains `browse: bool = False`
      + `user_data_dir: Optional[str] = None`. When `browse=True`: `headless=False`,
      use `launch_persistent_context` when `user_data_dir` set (else `launch + new_context`
      for `--incognito`), skip `_explore_round`, register `context.on("page")` (multi-tab),
      `page.on("framenavigated")` (refresh DOM snapshot on nav), `page.on("request")`
      (capture request side, additive), block on `browser.on("disconnected")` (user
      closes browser → capture done). Periodic `context.cookies()` snapshot every ~5s +
      on disconnect. Add `--browse`, `--profile <dir>`, `--incognito` to `with_live()`
      in `glyph/cli/_shared.py`; thread through `live_kwargs()`. Update `glyph/cli/run.py`
      `run_live` to NOT take over the screen with the dashboard during browse (user needs
      the browser visible) — print "Browser open — navigate, log in, do your flows. Close
      the browser when done." to stderr; AFTER browser-close run `_gather` + `_render`,
      THEN open dashboard as post-capture view (or print summary if `--no-tui`). Same
      plumbing for `glyph capture live --browse`. Update README live-capture section.
      Default profile dir: `~/.glyph/profiles/<host>/` (override via `GLYPH_PROFILE_DIR`
      env or `--profile <dir>`; `--incognito` = fresh ephemeral). Medium. See ADR-13.
- [ ] **Browse Mode: tests for the new code path** (added 2026-07-31 by Super Z, Session 19)
      — `tests/test_capture_live.py`: mock Playwright; assert `browse=True` →
      `launch(headless=False)` or `launch_persistent_context(headless=False)`; assert
      `_explore_round` NOT called when `browse=True`; assert `context.on("page")` registered
      (multi-tab path); assert `browser.on("disconnected")` is the wait condition; assert
      `page.on("request")` handler records the request side. Follow the existing
      `test_capture_live.py` mock-playwright pattern. Low-Medium. See ADR-13.
- [ ] **Browse Mode: `glyph profile clear <host>` CLI** (added 2026-07-31 by Super Z,
      Session 19) — convenience command to wipe a per-host Chromium profile dir
      (`~/.glyph/profiles/<host>/`) when the user wants to start fresh (logged-out, no
      cached state). Doc-only fallback for v1: document `rm -rf ~/.glyph/profiles/<host>/`.
      Low. See ADR-13.
- [ ] **Browse Mode: real-world verification on an auth-protected target** (added 2026-07-31
      by Super Z, Session 19) — the build session's end-to-end proof. Point `glyph run live
      --browse <user's-target>` at a real auth-protected site (the user's SIM/betting account
      flow is the obvious candidate), log in, navigate to deposit/withdraw/send, close the
      browser, confirm the captured catalog contains the auth + payment endpoints + the
      sensitive scan flags the credentials/tokens/OTPs in those flows. Document the result
      in the session review. Medium. See ADR-13.
- [ ] **Browse Mode: dedicated `cookies` table (v2)** (added 2026-07-31 by Super Z,
      Session 19) — v1 stashes the periodic `context.cookies()` snapshot as a JSON blob in
      meta (`capture_cookies`). v2 promotes it to a dedicated `cookies` table (schema bump)
      so `glyph sensitive` can flag auth tokens / session IDs in cookies per-target, and
      drift can track cookie changes between captures. Low-Medium. See ADR-13.
- [ ] **Browse Mode: split-pane TUI (browser + dashboard side-by-side)** (added 2026-07-31
      by Super Z, Session 19) — v1 opens the dashboard AFTER browser-close (post-capture
      exploration view). Future enhancement: split-pane mode where the dashboard is visible
      alongside the browser, streaming flows in real time as the user navigates. Needs
      Textual + visible-Chromium window-management work. Low — defer until v1 proves the
      capture path is solid. See ADR-13.

---
## 2026-07-31 — Session 19 cont. — ADR-14 supersedes ADR-13 (CDP-attach primary)

User feedback on ADR-13: wants their REAL browser (Brave primary, Edge secondary,
both Chromium) with saved logins/extensions/password manager — not a Glyph-managed
isolated profile. ADR-14 (proposed) switches the PRIMARY technique to CDP-attach
(`connect_over_cdp` to the user's running browser on `--remote-debugging-port=9222`);
ADR-13's `launch_persistent_context` becomes the FALLBACK. See ADR-14 + review
section 7. The build-session items below SUPERSEDE the ADR-13 build items above
for the authoritative implementation — read ADR-14, not ADR-13.

- [x] **Implement ADR-14: `--browse` with CDP-attach primary + launch fallback**
      (added 2026-07-31 by Super Z, Session 19 cont.; done 2026-07-31 by Super Z,
      Session 19 cont. 4, commit `8915b5d`) — `capture_url` now branches on
      `browse=True`; CDP-attach primary (`connect_over_cdp` → reuse
      `browser.contexts[0]` → `new_page`+`goto`), launch-fallback
      (`launch_persistent_context(channel='chrome'|'msedge', headless=False, ...)`;
      Brave via `executable_path` auto-detected per OS). `_make_recorders` shared by
      auto + browse: `page.on('response')`+`'request'` (additive)+`'websocket'`+
      `'framenavigated'`+`'popup'` (recurse). Tab-lineage scoping (url = target tab +
      popups; no url = all-traffic with stderr banner). Periodic `context.cookies()`
      snapshot. Stop: attach → Ctrl+C detaches (browser stays); launch → close/Ctrl+C.
      `capture_mode` meta. `--browse`/`--cdp-port`/`--cdp-host`/`--browser`/
      `--browser-path`/`--incognito`; url `nargs='?'`. `run.py` browse path: no TUI
      during capture, `_gather`+dashboard after. 10 new tests (mock Playwright), 156
      pass / 5 skip. Auto mode verified against example.com. See ADR-14.
- [x] **Browse Mode: `glyph browse --launch <browser>` helper** (added 2026-07-31 by
      Super Z, Session 19 cont.; done 2026-07-31, Session 19 cont. 4, commit
      `8915b5d`) — `glyph/cli/browse.py`: `--launch` spawns the chosen browser with
      `--remote-debugging-port=9222` (resolves the binary per OS via `find_browser`);
      no `--launch` prints attach help (per-browser one-liner + the attach command).
      `--browser-path` for explicit binaries. Registered in `cli/__init__.py`.
- [x] **Browse Mode: tests for CDP-attach + launch-fallback paths** (added 2026-07-31
      by Super Z, Session 19 cont.; done 2026-07-31, Session 19 cont. 4, commit
      `8915b5d`) — `tests/test_capture_live.py`: 10 new tests with mock-Playwright
      fakes (`_FakeChromium`/`_FakeBrowser`/`_FakeContext`/`_FakePage`). Covers:
      CDP-attach hooks target tab + popups + disconnect doesn't close the user's
      browser; all-traffic hooks every tab + `context.on('page')`; launch-fallback
      uses `channel='chrome'` + per-host profile; Brave without a binary raises a
      clear error; `--browse` flags in parser; `live_kwargs` carries browse options
      + `GLYPH_CDP_URL` override; `glyph browse` registered; auto mode still
      requires url. Blocking tests fire the `disconnected`/`close` event the driver
      listens for (not `_thread.interrupt_main`, which `Event.wait()` can swallow).
- [ ] **Browse Mode: real-world verification on Brave + an auth-protected target** (added
      2026-07-31 by Super Z, Session 19 cont.) — the build session's end-to-end proof on the
      user's PRIMARY browser. Launch Brave with `--remote-debugging-port=9222`, run
      `glyph run live --browse <user's-target>`, log in (Brave's saved logins + password
      manager), navigate to deposit/withdraw/send, Ctrl+C to detach, confirm the captured
      catalog contains the auth + payment endpoints + `glyph sensitive` flags the
      credentials/tokens/OTPs. Repeat on Edge as the secondary. Document the result + any
      Brave-Shields blocks in the session review. Medium. See ADR-14.
- [ ] **Browse Mode: mitmproxy `glyph capture proxy` for Firefox/Safari (future)** (added
      2026-07-31 by Super Z, Session 19 cont.) — CDP-attach is Chromium-only; Firefox/Safari
      users have no browse-mode path today (they use `glyph run har`). A future
      `glyph capture proxy` command starts `mitmdump -s glyph/capture/mitm.py`, adds a
      `websocket` handler to the addon (captures WS frames), and documents browser-proxy +
      cert-install per browser. ~100-150 LOC. Deferred until a Firefox/Safari user asks.
      Low-Medium. See ADR-14 + review section 7.

---
- [x] **TUI target picker** (added 2026-07-31 in the Session 18 follow-ups; completed Session 28, product commit `21d3739`) — the dashboard now opens a `t` picker over registered real targets, activates the selected target, reloads all views, excludes `(unassigned)`, and blocks switching while capture/analysis workers are active.


### Session 29 follow-ups (2026-08-01)
- [ ] Verify the real Playwright live TUI on Windows: startup, top-bar counts, streaming Flows/Data rows, final Schema/Rosetta population, and visible failure messages.
- [ ] Consider a bounded graceful-shutdown timeout/fallback for pathological browser/network hangs.
