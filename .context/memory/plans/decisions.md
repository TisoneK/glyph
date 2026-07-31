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

---
## ADR-6: Capture operates at the HTTP/application layer; raw packet (.cap/pcap) is out of core (2026-07-31)
- **Status:** accepted
- **Context:** The user asked whether Glyph should decode `.cap`/pcap packet captures. Research
  (see `reviews/2026-07-31-capture-mobile-scope-research.md`): `.cap`/`.pcap`/`.pcapng` are
  packet-level; mitmproxy has no native pcap I/O (it is an HTTP-layer proxy). Turning a pcap
  into HTTP needs TCP reassembly + TLS decryption (SSLKEYLOGFILE / a decrypting proxy) + HTTP
  parsing, and even `pyshark`+keylog often can't expose decrypted app-data cleanly. Packet-level
  only truly matters for non-HTTP protocols (custom TCP/UDP, MQTT, raw protobuf, un-MITMable
  QUIC/HTTP-3) — a different tool class (Wireshark + pbtk + Frida).
- **Decision:** Glyph captures and reasons at the **HTTP/application layer**. Substrates:
  HAR import, the Playwright browser driver (the DOM↔API pairing Rosetta needs), and the
  optional mitmproxy addon (wire-level HTTP incl. WebSocket frames). **Raw packet capture
  (.cap/.pcap/.pcapng) is not a core capability.** If a target ever genuinely requires it, it is
  handled by an *optional preprocessing adapter* that converts pcap → HTTP `Flow`s (tshark /
  PolarProxy with an SSLKEYLOGFILE) and feeds the same catalog — Glyph never parses raw packets
  itself. Non-HTTP binary/streaming protocol RE (custom TCP/UDP, MQTT, raw protobuf-over-h2c) is
  **out of scope**; Glyph's value is HTTP-semantic (endpoints, schemas, code↔label, DOM pairing).
- **Consequences:** The catalog's unit stays an HTTP request/response (+WS frame, +DOM). A pcap
  adapter, if built, is a thin importer producing `Flow`s — same interface as `capture/har.py`
  (keeps scapy/pyshark out of the core deps). Mobile/native TLS-pinned traffic is captured via
  mitmproxy+Frida-unpinning or PCAPdroid→pcap→adapter, not by Glyph sniffing packets.

---
## ADR-7: Mobile static mining handles the whole package family (APK/IPA + XAPK/APKS/APKM + OBB) (2026-07-31)
- **Status:** accepted (implementation backlogged)
- **Context:** The user asked for XAPK (and beyond) handling. Today `glyph/mobile/apk.py` mines a
  single APK/IPA (zip + regex over dex/so/resources). Research (same note): modern Android apps
  ship as **split APKs** (`base.apk` + `config.<abi|density|lang>.apk`); stores wrap these as
  **XAPK** (zip: base + splits + optional `Android/obb/` + `manifest.json`), **APKS**
  (bundletool APK Set), or **APKM** (APKMirror). Endpoint strings live across base dex/resources,
  split native `.so` libs, **and** OBB assets — so single-APK mining misses endpoints.
- **Decision:** The mobile stage treats an input as *"an archive that may contain one or more
  APKs plus OBB/asset blobs."* It mines APK/IPA directly, and for XAPK/APKS/APKM/zip-of-APKs it
  **recursively unwraps** and mines **every** inner APK (dex + native `.so` + resources) plus
  scans OBB/asset entries for URLs and API paths. It does **not** install, run, device-target,
  or merge splits (no bundletool/adb) — static string mining only. Developer-side **AAB** is out
  of scope (you get APKs from stores, not AABs). IPA is handled as its own zip (Mach-O/plist);
  IPA **decryption** stays out of scope (needs a jailbroken device, RESEARCH-DEEP-DIVE §7.3).
- **Consequences:** `glyph mobile` becomes format-agnostic — point it at any store download
  (`.apk/.xapk/.apks/.apkm/.ipa`) and it mines everything. Implementation: detect a bundle
  (multiple `.apk` entries, a `manifest.json`, or an `Android/obb/` dir) and recurse one level;
  add split `.so` and OBB assets as scan surfaces; keep the existing per-entry size cap.
  Tracked as an implementation item in `tasks/backlog.md`.

---
## ADR-8: `rich` is the CLI rendering layer + the package's one runtime dependency (2026-07-31)
- **Status:** accepted (amends ADR-2's "zero third-party deps")
- **Context:** The user wanted advanced, *designed* terminal output — real tables, panels,
  consistent color that works on all platforms (they were on Windows PowerShell seeing plain
  output). `colorama` only shims Windows ANSI; it has no tables. Hand-rolled ANSI (Session 12/13)
  was fragile and still looked like debug lines. ADR-2 set a zero-dependency base.
- **Decision:** Adopt **`rich`** as the CLI's rendering layer and the package's single runtime
  dependency (`rich>=13`). It is pure-python, lightweight, and handles Windows VT, `NO_COLOR`,
  and non-TTY/pipe detection itself. **The importable library core stays dependency-free:** rich
  is imported only by `glyph.cli` (via `glyph/cli/_console.py`), never by the stage packages, and
  a `HAS_RICH` flag falls back to plain rendering if it is somehow absent. Heavy backends
  (mitmproxy/Playwright/genson/duckdb) remain optional extras.
- **Consequences:** `pip install glyph-re` now pulls rich (+ its small dep tree); `import glyph`
  still needs nothing third-party. `run` renders a panel; `sensitive`/`dict` render rich tables
  with severity color-coding. This amends ADR-2: the base is "one lightweight presentation dep
  (rich); the library core remains stdlib-only." `_format.py`'s ANSI helpers are retained for the
  no-rich fallback and for the analyzer commands not yet migrated (fingerprint/auth/gating/catalog
  still use the plain tree renderer — a follow-up could move them to rich tables).

---
## ADR-9: The TUI is a presentation layer over glyph.db; the engine stays headless (2026-07-31)
- **Status:** accepted (Phase 1 implemented; live streaming = Phase 2)
- **Context:** The user wants `glyph run live` to leave you inside an interactive terminal
  dashboard where captured data is visible and navigable — "watching the site being
  reverse-engineered," not a printed report. The backend already produces all the data
  (flows, DOM labels, schema, findings, dictionary in `glyph.db`); the missing piece is a
  visualization/exploration layer, not more analyzers.
- **Decision:** Add a **Textual TUI** (`glyph.tui`) that is a *pure presentation/interaction
  layer over the catalog* — it only reads `glyph.db` and never discovers/analyzes anything.
  `glyph.tui.data` holds pure catalog adapters (flows/dom/schema/sensitive/rosetta rows +
  summary); `glyph.tui.app` is the Textual app. Textual is an optional **`[tui]` extra**
  (depends on rich, already core; `HAS_TEXTUAL`-guarded). Commands: `glyph dashboard [--db]`
  opens the TUI on any catalog; `glyph run live` opens it after capture when interactive
  (TTY + textual), else prints the summary (or `--no-tui`); new `glyph flows` / `glyph dom`
  read-commands mirror `dict`/`sensitive`. **Phasing:** Phase 1 (now) = read-only exploration
  over a completed catalog — 5 tabbed views + flow request/response drill-in. Phase 2 = true
  live streaming (the capture driver writes flows incrementally + the TUI auto-refreshes),
  which needs concurrency changes to `capture/driver.py` and is deferred.
- **Consequences:** The analysis engine stays usable headless (CLI/CI/scripts/codegen
  unaffected) — the TUI is a frontend, not a dependency of the pipeline. Data limitations to
  address in Phase 2: DOM harvest only captures elements with *direct text*, so forms/inputs
  are under-represented (a capture enhancement); flow byte sizes fall back to response-body
  length when Content-Length is absent.

- **Phase 2 implemented (2026-07-31, Session 15):** live/real-time. The capture driver writes
  flows/WS frames + DOM snapshots to `glyph.db` incrementally and sets a `capture_status` meta;
  the catalog runs on WAL + busy_timeout for concurrent read/write; the dashboard runs the
  capture in a worker thread and refreshes flows/DOM/summary every 1s (+ analysis every 3s) with
  a `● LIVE`/`✓ captured` header. `glyph run live` opens the live dashboard when interactive;
  `--no-tui`/pipe keeps the synchronous headless path. Verified via async `run_test` (flows
  stream 0→N, header flips); the Playwright browser live path is confirmed on-device.

- **Home screen added (2026-07-31, Session 15):** bare `glyph` opens a home/splash screen (the
  GLYPH ANSI-shadow wordmark + URL box + Capture/Open/Quit) that flows into the live dashboard;
  Esc returns home. The TUI is now `GlyphApp` hosting `HomeScreen` + `DashboardScreen` (+ a
  `FlowDetail` modal). Subcommand is optional — bare `glyph` opens home when interactive, else
  prints help. `dashboard`/`run live`/`flows`/`dom` jump straight to their views. Still a pure
  presentation layer over glyph.db.

---
## ADR-10: SNI bug-host hunting is a bounded active-recon stage, post-sensitive (2026-07-31)
- **Status:** accepted (implemented 2026-07-31, Session 16)
- **Context:** The user wants Glyph to hunt for "SNI bug hosts" — hostnames that, when used as
  the TLS SNI, are zero-rated or otherwise pass through a carrier's DPI for free-internet
  tunneling (HttpInjector / KPN Tunnel / HA Tunnel class of tools, Kenya-priority). The user's
  explicit framing: "Ignore those that are already found sites eg txt files etc. This is
  completely how to find a new host by reverse-domain, cloudflare etc." So the stage must
  DISCOVER new candidates from the live capture, NOT scrape published bughost.txt lists. The
  existing `sensitive` stage (ADR-4) is strictly passive over the captured catalog; SNI hunting
  fundamentally requires *active reconnaissance* (DNS resolution, CT log queries, reverse-IP
  lookups, optional TLS-SNI probe) — it cannot be done from captured traffic alone.
- **Decision:**
  1. **New stage `glyph.snihunt`** — bounded active recon over the captured host surface:
     - `extract` — pull every SNI/host + IP observed in the capture (flow `host`, `:authority`,
       `Host` header, captured cert CN/SAN when present).
     - `dns` — DoH resolution (Google `dns.google` + Cloudflare `cloudflare-dns.com`) with a
       short cache + 5-8s timeouts; falls back to system `socket.getaddrinfo`.
     - `reverseip` — reverse-IP lookup via the HackerTarget `reverseiplookup` API to find
       sibling hostnames sharing the same IP (the "reverse-domain" technique the user named).
     - `ctlogs` — Certificate-Transparency subdomain enumeration via certspotter (primary) and
       crt.sh (fallback); bounded per-domain cap, 429-aware.
     - `cdn` — CDN / frontable-edge detection: Cloudflare (AS13335 + the published IPv4/IPv6
       ranges), Fastly, Akamai, AWS CloudFront. A host on a CDN edge is "frontable" — the SNI
       can be set independently of the tunnel destination (the "cloudflare" technique the user
       named).
     - `zerorate` — zero-rating heuristics: known free/social TLD patterns
       (`0.facebook.com`, `free.facebook.com`, `0.wikipedia.org`, `*.internet.org`,
       operator free-pack domains) + wildcard-cert coverage + short TTL signals.
     - `probe` (optional, default off) — opens ONE TLS handshake with the candidate as SNI to
       a public CDN edge and records the served cert's CN/SAN. Exactly what a browser does;
       no port scanning, no exploitation.
     - `hunt` — orchestrator: runs the hunters, scores each candidate (0-100), persists as
       `Finding(kind="sni_bug_host", category=...)` with score + evidence.
  2. **Bounded active-recon rules (the scope fence):**
     - Read-only public APIs only (DNS, CT logs, reverse-IP). No exploitation, no auth bypass.
     - The only active connection is ONE TLS handshake per probe candidate, to a public CDN
       edge — identical to what a browser does on every page load. No port scanning, no
       fingerprinting beyond the cert CN/SAN.
     - Per-domain rate limit + short timeouts (5-8s); honors HTTP 429.
     - `--no-net` disables ALL network hunters; the stage still runs local heuristics over the
       captured surface (extract + embedded CDN ranges + zero-rating patterns).
     - `--probe` is opt-in (default OFF); without it the stage is read-only recon.
  3. **Runs after `sensitive`, opt-out via `--no-snihunt`.** `glyph run live`/`run har` now run
     capture → schema → rosetta → sensitive → snihunt. `--no-sensitive` and `--no-snihunt` are
     independent opt-outs.
  4. **New finding kind** `FINDING_SNI_BUG_HOST = "sni_bug_host"` (free TEXT column — no schema
     migration). Categories: `sni_candidate`, `sni_frontable_cdn`, `sni_zero_rated`,
     `sni_shared_cert`. `value_sample` = the candidate SNI hostname; `evidence` = score + the
     signals that fired.
  5. **New TUI tab** (key 6, "SNI Hunt") + new `glyph snihunt` CLI command (`--target`,
     `--no-net`, `--probe`, `--min-score`, `--json`).
  6. **Authorization stays with the user** (RESEARCH.md §10). Glyph surfaces candidates; it
     does not build tunnels, does not name a tunneling tool (ADR-3), and does not test against
     a specific carrier's billing system — that is the user's call.
- **Consequences:**
  - `glyph.snihunt` is the ONE active-recon stage; every other stage stays passive. This is a
    deliberate scope expansion of ADR-4's "passive only" clause, called out here so future
    agents don't relitigate it.
  - Tests run fully OFFLINE: each network hunter takes a swappable `http_get` callable, so
    `test_snihunt.py` injects a fake and asserts on shape, not on the live internet.
  - The catalog `findings` table gains a new `kind` value; `is_noise()` treats `sni_bug_host`
    findings as never-noise (they are the point of the stage, like sensitive-data findings).
  - The user handles per-target legal/authorization; SNI bug-host candidates are advisory.
- **Supersedes:** nothing. Amends ADR-4 (the sensitive stage stays passive; the active-recon
  scope lives in `snihunt`, a separate stage).

---
## ADR-11: VPN-Config Decoder — borrows InjectX algorithms, file-triggered, [crypto] extra (2026-07-31)
- **Status:** proposed (implementation in progress, Session 17)
- **Context:** The user wants a VPN-Config Decoder/Sniffer: a user supplies a config file
  (.hc / .ehi / .dark / .ziv / .tls / etc.) and Glyph decrypts it (online or offline) into a
  normalized view of the tunnel's host/port/protocol/SNI/bug-host/credentials. The user has
  already built most of this in a SEPARATE project, InjectX (https://github.com/TisoneK/InjectX)
  — we are BORROWING its algorithms (the crypto schemes, the key store, the format detector),
  NOT coupling to or importing from it. InjectX is a standalone Electron+Python app; Glyph is
  a CLI/TUI library. The algorithms are public (Pancho7532/HCDecryptor, HCTools/hcdecryptor,
  X-Tools) — reverse-engineered from the VPN apps' APKs (HTTP Custom, HTTP Injector, HA Tunnel,
  DARK Tunnel, ZIVPN, TLS Tunnel). The user's explicit framing: "we are borrowing algorithms
  not combining the projects."
- **Decision:**
  1. **New stage `glyph.vpndec`** — ports InjectX's decrypt algorithms into Glyph's conventions:
     - `keys.py` — the Pancho7532 key store (ePro/evozi/slipk/tls/aot/npv2/vhd/sip), with an
       external keyfile merge (GLYPH_VPNKEYFILE env, like InjectX's INJECTX_KEYFILE).
     - `detect.py` — format detector (extension + content features: entropy, ASCII ratio,
       base64 likelihood, ZIP magic) → a `Format` enum.
     - `crypto.py` — crypto primitives (AES-ECB/CBC/GCM, ChaCha20, PBKDF2, XOR, custom-b64)
       behind a `HAS_CRYPTO` flag (pycryptodome). Graceful fallback: if pycryptodome is absent,
       the stage reports `no_decryptor` for crypto-dependent formats but still decodes plain
       ones (DARK envelope, OVPN, plain JSON).
     - `hc.py` (A1-A4), `ehi.py` (B1), `dark.py` (I1), `ziv.py` (H1), `tls.py` (F1) — the five
       formats the user has sample configs for. Architecture is extensible (HAT/NPV/NSH/VHD
       port as backlog follow-ups).
     - `router.py` — scheme router (format → applicable schemes → best-confidence result).
     - `normalize.py` — normalize decrypted JSON/XML → a `VpnConfig` dataclass (host, port,
       protocol, sni, bug_host, ssh creds, payload, proxy, dns, raw fields).
  2. **`[crypto]` extra (pycryptodome).** Consistent with `[live]`, `[tui]`, `[schema]`,
     `[analytics]` — the base package stays stdlib+rich; vpndec's crypto needs an optional dep.
     `HAS_CRYPTO` guard, same pattern as `HAS_RICH`/`HAS_TEXTUAL`.
  3. **File-triggered, NOT auto-run.** `glyph vpndec <file>` is the entrypoint — unlike
     snihunt (which auto-runs after sensitive on a live capture), vpndec operates on a FILE the
     user points at, not on captured traffic. It does not run in `glyph run live`/`run har`.
     The decrypted config is persisted to a new `vpn_configs` table in the catalog; the TUI tab
     reads from there. `glyph vpndec <file>` decrypts + stores + prints; `glyph dashboard` shows
     it in the TUI.
  4. **New catalog table `vpn_configs`** (filepath, filename, format, scheme, status, confidence,
     host, port, protocol, sni, bug_host, ssh_server, ssh_port, ssh_user, ssh_pass, proxy_host,
     proxy_port, payload, dns, raw_json). Decrypted credentials are KEPT (ADR-4 precedent —
     flag-and-keep; the catalog is a sensitive artifact the user owns).
  5. **New TUI tab** (key 7, "VPN Dec") + `glyph vpndec` CLI command (`--json`, `--keyfile`,
     `--all-schemes`, `--db`).
  6. **Authorization stays with the user** (RESEARCH.md §10). Glyph decodes configs the user
     already possesses; it does not distribute keys, does not build tunnels, and names no
     tunneling tool (ADR-3). The user owns per-target legal authorization.
- **Consequences:**
  - `glyph.vpndec` is the second file-based stage (after `glyph mobile`, which mines APK files).
    It is NOT part of the capture pipeline.
  - Tests run with pycryptodome installed (it's in `[dev]`); the `HAS_CRYPTO=False` path is
    tested too (a plain DARK envelope decodes without crypto).
  - The catalog gains a `vpn_configs` table (schema bump); existing catalogs migrate additively.
  - InjectX is credited in the code comments as the algorithm source; no InjectX code is
    imported, and InjectX remains a separate project (per the user's explicit instruction).
- **Supersedes:** nothing.
