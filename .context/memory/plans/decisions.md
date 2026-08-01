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
- **Status:** accepted (implemented 2026-07-31, Session 17)
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

---
## ADR-12: Multi-target catalog — `targets` table + `target_id` on every data row (2026-07-31)
- **Status:** accepted (implemented 2026-07-31, Session 18)
- **Context:** Through Session 17 the catalog was single-target: `meta.target_host` held the
  one host, and every `glyph run`/`run live`/`snihunt`/TUI-capture called `Catalog.reset()`
  which wiped ALL data tables + meta (except `schema_version`). Re-capturing a different
  target destroyed the previous one. The user's directive (Session 18): "the db should have
  rows of target in the tables (target id)" — i.e. multi-target coexistence with a `targets`
  table and a `target_id` on every data row, instead of wiping the DB each run.
- **Decision:**
  1. **New `targets` table** — registry of every host ever captured (`id`, `host` UNIQUE,
     `label`, `notes`, `created_at`). `id INTEGER PRIMARY KEY` (no AUTOINCREMENT) so the
     reserved id=0 "(unassigned)" sentinel is insertable; real targets get ids >= 1.
  2. **`target_id` column on every data table** — flows, endpoints, fields, dictionary,
     page_observations, findings, vpn_configs. Every UNIQUE constraint now includes
     `target_id` (e.g. endpoints → `UNIQUE (target_id, method, host, path_template)`,
     findings → `UNIQUE (target_id, kind, category, endpoint_id, location)`,
     vpn_configs → `UNIQUE (target_id, filepath)`).
  3. **Reserved "(unassigned)" target (id=0).** Every write stamps a NON-NULL `target_id`
     (explicit > active > unassigned=0). This is required because SQLite treats `NULL != NULL`
     in UNIQUE constraints, so nullable `target_id` would break upsert dedup (two flows with
     NULL target_id + the same endpoint shape would NOT collapse). Rows written without
     `set_target` (legacy tests, REPL scratch) land in unassigned and still dedup correctly.
  4. **`Catalog._active_target_id` instance state.** `set_target(host)` upserts into `targets`
     + activates (returns the id); writes stamp it; reads filter to it by default (fall back
     to "all targets" when no target is active). `clear_active_target()` / `set_active_target(id)`
     switch without creating.
  5. **`clear_target(target_id=None)` replaces `reset()` at every run site.** Wipes ONLY the
     active (or specified) target's rows; keeps the target row in `targets`; keeps every other
     target's data. `reset()` is retained for tests + a future `--reset` flag (full wipe).
  6. **Reads take `target_id` + `all_targets` params.** Default: filter to active if set, else
     all. `all_targets=True` forces all. This means `glyph sensitive` (no `--target`) scans
     every target's flows; `glyph sensitive --target <host>` scans one. The TUI shows all
     targets' data mixed (a future target picker can filter — out of scope here).
  7. **`glyph target list|show|rm` CLI** — the management surface. `list` shows every target
     + its flow count; `show <host|id>` prints per-target row counts; `rm <host|id> --yes`
     deletes a target AND every row that belongs to it.
  8. **Schema v3 → v4 migration.** `_migrate_to_v4` rebuilds each data table that lacks
     `target_id` (SQLite can't ALTER a UNIQUE) via create-copy-drop-rename, ports legacy
     NULL `target_id` rows to the unassigned bucket (id=0), and ports the old
     `meta.target_host` into a real `targets` row (label="migrated"). Idempotent + per-table
     (a mixed old/new DB rebuilds only the old tables). Indexes split out of `_SCHEMA` into
     `_INDEXES` so the `target_id` indexes don't fire before migration adds the column.
- **Consequences:**
  - `glyph run har`/`run live`/`snihunt`/TUI-capture no longer nuke the catalog — they
    activate + clear ONE target. Capturing betika.com then sportybet.com leaves both in the
    DB, each queryable via `glyph target show <host>` and filterable via `--target`.
  - `glyph capture har`/`capture live` keep ACCUMULATE semantics (no clear) — `capture` is
    "add traffic," `run` is "fresh analysis of this target." The split is explicit.
  - The "(unassigned)" target is visible in `glyph target list` (label="unassigned"). It's
    the bucket for rows written without `set_target`; users can `glyph target rm 0` to clear
    scratch rows. `target()`'s fallback skips it so the TUI sub_title doesn't read
    "(unassigned)" when only scratch rows exist.
  - `endpoints` are now per-target (two targets hitting `GET api.x.com/users/{id}` get two
    endpoint rows). This is slightly less normalized than the old shared-endpoint model but
    matches the user's "every row has target_id" framing and makes per-target cleanup trivial.
  - Tests: `test_run_resets_catalog_between_targets` was rewritten to
    `test_run_coexists_across_targets` (the old "run wipes between targets" assertion is now
    wrong by design). Two new tests cover multi-target coexistence + the unassigned dedup.
- **Supersedes:** nothing. Amends the implicit single-target model that ran from Session 1
  through Session 17 (the `meta.target_host` + `Catalog.reset()` pattern).

---
## ADR-13: Browse Mode — Playwright visible, user-driven, persistent context (2026-07-31)
- **Status:** proposed → **superseded by ADR-14 before implementation** (2026-07-31, Session 19 cont.). ADR-14 switches the PRIMARY technique from Playwright-launched Chromium to CDP-attach to the user's real browser (Brave/Edge/Chrome). ADR-13's launch-persistent-context design is retained as the FALLBACK in ADR-14. Read ADR-14 for the authoritative decision; this entry is kept for the research trail.
- **Context:** `glyph run live <url>` today launches Chromium **headless** and auto-drives
  the page via `_explore_round` (scroll + pseudo-random generic clicks on `a, button,
  [role=button], [class*='item']` etc.). This captures anything reachable by generic
  click/scroll on the landing page (public catalogue APIs, lazy-loaded lists, live-odds
  streams, SPAs whose data loads on initial render) but CANNOT capture:
  - **Auth/login flows** — no form filling, no credential submission, no OTP.
  - **Payment / deposit / withdrawal flows** — require amount entry, provider selection,
    PIN/OTP confirmation, modal/wizard navigation.
  - **Send/transfer flows** — multi-step forms (recipient → amount → review → confirm).
  - **Account-state-specific endpoints** — `/api/wallet/balance`, `/api/transactions`,
    `/api/profile` (return 401 unauthed, full of value once logged in).
  - **KYC / verification flows** — modal wizards, document upload.
  - **Hidden / modal flows** — behind "click to deposit" buttons generic clicks won't aim at.
  The user's directive: *"A browser pops up, the user interacts with it while the live
  capture is continuing — same as `glyph run live` but with real browser and user actually
  navigates."* The *capture mechanism* doesn't need to change (Playwright's response/WS
  hooks fire on every response regardless of who initiated the navigation); the *driving*
  changes from auto-explore to human-driven.
- **Decision:**
  1. **New `--browse` flag** on `glyph run live` and `glyph capture live`. When set:
     - `capture_url(browse=True, user_data_dir=<per-host profile>)`.
     - `launch_kwargs["headless"] = False` — browser visible.
     - Use `browser_type.launch_persistent_context(user_data_dir, headless=False, ...)`
       when `user_data_dir` is set (login persists across captures); else fall back to
       `launch(headless=False) + new_context()` for `--incognito`.
     - Skip `_explore_round` (the user is driving; auto-clicks would fight them). The
       `--explore N` flag stays as an opt-in if the user wants both (rare).
     - Register `context.on("page", ...)` so new tabs the user opens (Ctrl+click,
       `target="_blank"`, "open in new tab") get the same response/WS/snapshot handlers.
     - Register `page.on("framenavigated", ...)` to refresh the DOM snapshot on nav
       (link click, form submit, address-bar nav within the page) — keeps
       `page_observations` current for Rosetta.
     - Register `page.on("request", ...)` (NEW) to capture the request side. Today only
       responses are recorded; this catches requests whose responses never arrive
       (cancelled, preflight-rejected, beacon fire-and-forget). Purely additive.
     - Block on `browser.on("disconnected", ...)` (or `context.on("close")`) — user
       closes the browser, `capture_status = "done"`, analysis runs. Ctrl+C in the
       terminal calls `browser.close()` as a fallback.
     - Periodic `context.cookies()` snapshot (every ~5s + on disconnect) — `document.cookie`
       reads are invisible to the response hook. v1: stash as a JSON blob in meta
       (`capture_cookies`); v2: dedicated `cookies` table (schema bump, deferred).
  2. **Per-host profile dir.** Default `~/.glyph/profiles/<host>/` (override via
     `GLYPH_PROFILE_DIR` env or `--profile <dir>` flag; `--incognito` uses a fresh
     ephemeral context). Login survives across `glyph run live --browse <host>`
     invocations on the same target. Aligns with ADR-12's per-target model — one
     Chromium profile per target host.
  3. **TUI integration.** When `--browse` is set, do NOT take over the screen with the
     dashboard DURING capture (the user needs the actual browser visible). Print a
     one-line "Browser open — navigate, log in, do your flows. Close the browser when
     done." to stderr. AFTER browser-close: run `_gather` (schema → rosetta → sensitive
     → snihunt), THEN open the dashboard as a post-capture exploration view (or print
     the summary if `--no-tui`). Split-pane (browser + dashboard side-by-side) is a
     future enhancement; defer.
  4. **Cookie/session persistence** via `launch_persistent_context` — log in once, all
     future runs on the same host start already-authed. The user can clear the profile
     via `glyph profile clear <host>` (or just `rm -rf ~/.glyph/profiles/<host>/`).
  5. **Captured flows are tagged `source = "playwright:<type>"`** (same as today). Add a
     `capture_mode` meta (`"auto"` vs `"browse"`) so the catalog/UI can distinguish
     auto-explore captures from user-driven captures if the user wants to filter.
  6. **Backward compatible.** `--browse` is opt-in; existing `glyph run live` behavior
     (headless + auto-explore + live dashboard takeover) is unchanged.
- **Consequences:**
  - The live capture path stays the SAME when `--browse` is NOT set — no regression.
  - A persistent profile dir means cookies/localStorage/IndexedDB survive across captures.
    Document the path + add `glyph profile clear <host>` (or document `rm -rf`).
  - Captures in browse mode can run for many minutes (the user is doing real flows) — the
    capture worker thread must handle long runs gracefully (the existing 1s/4s TUI tick
    + WAL catalog hold up; the periodic cookie snapshot adds a small write every 5s).
  - When `--proxy` is set, Chromium auto-disables QUIC (proxy can't speak QUIC) — non-issue.
    When NO proxy, QUIC traffic IS captured by Playwright's response hook (browser-layer).
  - Honest gaps (documented in the research note): non-browser traffic (mobile companion
    apps, desktop clients) is NOT captured — out of scope; covered by `glyph capture har`
    or the future pcap→HTTP adapter (ADR-6). Some service-worker/beacon traffic MIGHT slip
    past `page.on("response")` — mitigated by also hooking `page.on("request")`.
  - `glyph sensitive` will surface PII (passwords, OTPs, card numbers via Luhn) in the
    captured auth/payment flows — this is the POINT of the feature. The values are kept
    (ADR-4 precedent: flag-and-keep; the catalog is a sensitive artifact the user owns).
    Redaction, if wanted, is an export-time concern (backlog).
- **Research backing:** `.context/memory/reviews/2026-07-31-browse-mode-research.md`
  evaluates four techniques — Playwright visible (recommended), mitmproxy (rejected for
  v1: no DOM, cert-install friction, pinning breakage), hybrid (deferred), other (CDP /
  Selenium / extensions / Frida / Wireshark — all rejected). The recommendation is
  Technique A (Playwright visible): minimum disruption (~50-100 LOC), no new deps,
  decrypted bodies for free, DOM stays, multi-tab support, cookie/session persistence.
- **Supersedes / amends:** nothing. Builds on ADR-6 (HTTP/application layer — Playwright
  is the canonical implementation), ADR-9 (TUI as presentation — dashboard opens
  post-capture in browse mode), ADR-12 (multi-target — browse mode still respects
  `set_target` + `clear_target`). The build session must NOT change ADR-9's live-dashboard
  takeover for the non-browse path; browse mode is a sibling path, not a replacement.

---
## ADR-14: Browse Mode — CDP-attach to the user's real browser is primary; Playwright-launched Chromium is fallback (2026-07-31)
- **Status:** accepted (implemented 2026-07-31, Session 19 cont. 4)
- **Context:** ADR-13 (proposed, unimplemented) chose Playwright-launched Chromium
  (`launch_persistent_context`, headless=False, dedicated Glyph-managed profile) as the
  browse-mode technique. User feedback: they want their **real browser** (Brave primary,
  Edge secondary — both Chromium) with saved logins, password manager, extensions,
  bookmarks, autofill. For auth/payment flows, the real browser already has the credentials
  saved; re-entering them in a Glyph-managed isolated profile defeats the point and is a
  security smell (credentials typed into an unfamiliar profile). ADR-13's analysis also
  under-weighted "use the user's real browser" as an axis — it compared Playwright-Chromium
  vs mitmproxy vs hybrid, but not "attach to the user's running browser via CDP" vs "launch
  a real-browser binary". The refined research (review section 7) evaluates all three
  real-browser techniques: mitmproxy system proxy, Playwright `connect_over_cdp` attach,
  Playwright `launch_persistent_context(channel=...)` real-binary launch.
- **Decision:**
  1. **PRIMARY: CDP-attach to the user's real browser.** Glyph calls
     `playwright.chromium.connect_over_cdp("http://localhost:<port>")` to ATTACH to the
     user's already-running Chromium browser (Chrome/Edge/Brave) launched with
     `--remote-debugging-port=9222`. Glyph does NOT own the browser lifecycle — it observes.
     Registers `page.on("response")` / `page.on("request")` (additive — captures the request
     side, including requests whose responses never arrive) / `page.on("websocket")` /
     `page.on("framenavigated")` (refresh DOM snapshot on nav) on every existing tab;
     `context.on("page")` for new tabs. DOM via `page.content()`. Periodic
     `context.cookies()` snapshot (every ~5s + on detach). The user browses normally with
     their real session — saved logins, extensions, password manager, all of it.
  2. **FALLBACK: Playwright launches a real-browser binary.** When CDP-attach isn't
     available (no debug port reachable, or user wants a clean dedicated profile), Glyph
     spawns the installed browser via `launch_persistent_context(headless=False,
     user_data_dir=~/.glyph/profiles/<host>/, channel=<chrome|msedge>)`. This is ADR-13's
     original design, refined to use the real browser binary (`channel="chrome"` or
     `channel="msedge"`) instead of bundled Chromium. For Brave: `executable_path` to the
     Brave binary (Playwright has no `channel="brave"`) — auto-detect per OS (macOS
     `/Applications/Brave Browser.app/Contents/MacOS/Brave Browser`, Linux
     `/usr/bin/brave-browser`, Windows `%ProgramFiles%\BraveSoftware\Brave-Browser\
     \Application\brave.exe`) or `--browser-path <path>`.
  3. **`--browse` flag** on `glyph run live` and `glyph capture live`. The target `<url>`
     is OPTIONAL — present = target-tab + popups capture (point 7 default); absent =
     all-traffic capture (point 7 fallback). When set, Glyph TRIES CDP-attach first
     (default `http://localhost:9222`, overridable via `--cdp-port` / `--cdp-host` /
     `GLYPH_CDP_URL` env). If no CDP endpoint reachable, falls back to the launch path
     with a clear stderr message ("No browser on :9222 — launching <browser> with a
     dedicated profile; log in once, it persists at ~/.glyph/profiles/<host>/."). `--browser
     chrome|edge|brave` picks the fallback browser (default: chrome). `--incognito` forces
     an ephemeral context. `--no-browse` is implicit (current behavior).
  4. **Browser-launch helper (recommended).** `glyph browse --launch <browser> [--url <url>]`
     spawns the chosen browser with `--remote-debugging-port=9222`, resolving the binary
     per OS. If the browser is already running on that profile (profile-lock), it prints the
     attach instruction instead of failing. This is UX sugar; the manual path (user launches
     their own browser with the flag) is documented and works.
  5. **Stop signal differs by mode.**
     - CDP-attach: **Ctrl+C in the terminal detaches** (`cdp_connection.close()`) — the
       browser stays open, the user's session (all their tabs) is preserved. Closing the
       browser also stops capture. Detach-not-close is the default because closing the
       user's whole browser is disruptive.
     - Launch fallback: closing the browser stops capture (natural). Ctrl+C calls
       `browser.close()` as a fallback.
  6. **TUI integration.** When `--browse` is set, do NOT take over the screen with the
     dashboard DURING capture (the user needs the actual browser visible). Print a one-line
     "Attached to <browser> on :9222 — navigate, log in, do your flows. Ctrl+C here when
     done (browser stays open)." to stderr. AFTER detach/browser-close: run `_gather`
     (schema → rosetta → sensitive → snihunt), THEN open the dashboard as a post-capture
     exploration view (or print the summary if `--no-tui`). Split-pane (browser + dashboard
     side-by-side) is a future enhancement; defer.
  7. **Capture scoping — target-tab + popups by default; ALL tabs if no target
     (the user's filter requirement, with an explicit all-traffic fallback).**
     `--browse` takes the target `<url>` as OPTIONAL (not required). Two modes:
     - **Default (target given, e.g. `glyph run live --browse https://betika.com`):**
       target-tab + popups only. Glyph opens a fresh tab in the attached context
       (`context.new_page()` → `page.goto(url)`, shares the user's session: cookies,
       saved logins, password manager), hooks that tab + `page.on("popup")` (new tabs
       opened FROM it — payment providers, SSO, `target="_blank"`). Existing tabs +
       manually-opened new tabs are NOT hooked → the user's email/social/other-banking
       tabs are invisible by construction. This is the user's "filter non-relevant tabs"
       default.
     - **All-traffic fallback (no target, e.g. `glyph run live --browse` with no url):
       hook every tab.** On CDP-attach: iterate `context.pages` (every existing tab) +
       `context.on("page")` (every new tab), register the response/request/websocket/
       framenavigated hooks on each. The catalog has no active target set (or uses the
       reserved "(unassigned)" bucket, id=0 — ADR-12) since there's no anchor host;
       flows are tagged by their actual host and queryable via `--target <host>` later
       or `glyph target list` to see every host captured. Use this when the user wants
       a firehose capture of whatever they're doing across tabs (rare, but the user
       explicitly wants it available). The CLI MUST warn clearly when this mode is
       active: stderr banner "⚠ browse-all mode: capturing EVERY tab in your browser
       (email, social, other-banking — everything). Ctrl+C to stop." so it's never
       accidental.
     - **Launch fallback:** target given → same target-tab + popups model (Glyph owns
       the browser, opens the URL, hooks page + popups). No target → opens a blank page,
       hooks it + popups (the user navigates manually from there); or refuses with a
       clear message if all-traffic in a Glyph-launched browser doesn't make sense
       (likely refuses — launch mode owns the browser, so "all tabs" = "the one tab
       Glyph opened"; the all-traffic fallback is really an attach-mode concept).
     - **Navigations within a hooked tab** to other hosts (SSO redirect to
       `accounts.google.com`, payment redirect to `flutterwave.com`) ARE captured (the
       tab is still hooked) and tagged by their actual host. When a target is set, the
       target host is registered via `catalog.set_target(urlparse(url).hostname)`
       (ADR-12) so per-target read filtering works.
     - This gives the user both: the clean filtered default (target-tab + popups) AND
       the explicit all-traffic fallback (no target). The choice is a CLI-level UX
       decision (url present vs absent), not a separate flag — simplest mental model.
       A future `--browse-scope all|target` flag could make it explicit if the
       url-absent = all-traffic rule proves surprising.
  8. **Captured flows tagged `source = "playwright:<type>"`** (same as today). Add a
     `capture_mode` meta (`"auto"` vs `"browse-attach"` vs `"browse-launch"`) so the
     catalog/UI can distinguish.
  9. **Backward compatible.** `--browse` is opt-in; existing `glyph run live` behavior
     (headless + auto-explore + live dashboard takeover) is unchanged.
- **Consequences:**
  - CDP-attach means Glyph does NOT own the browser lifecycle — it observes the user's real
    session. This is the user's explicit preference (Brave primary, Edge secondary). Both
    are Chromium → CDP-attach works for both. Firefox/Safari are NOT supported by this path
    (not Chromium, no CDP) — those users use `glyph run har` (exists today) until a future
    `glyph capture proxy` (mitmproxy) lands.
  - **Brave:** CDP-attach works (Brave is Chromium). Launch fallback needs `executable_path`
    (no `channel="brave"`) — auto-detect per OS or `--browser-path`. Brave's built-in
    Shields may block some requests; document that the user can disable Shields for the
    target site if a capture looks incomplete.
  - **Stop signal is Ctrl+C (detach) in CDP-attach mode**, NOT browser-close — because
    closing the user's whole browser (all tabs) is disruptive. This differs from ADR-13's
    launch-mode "close the browser to stop". The build session must implement BOTH stop
    paths and pick the right one per mode.
  - **Security:** attaching to the user's real browser means Glyph COULD see their real
    cookies/tokens for ALL tabs — but the tab-lineage filter (point 7) means Glyph only
    hooks the target tab + its popups, so unrelated tabs (email, social, other-banking)
    are invisible by construction. Flows within the target tab that cross to other hosts
    (SSO/payment redirects) ARE captured and tagged by host; the catalog's multi-target
    model (ADR-12) + `--target <host>` read-filter handle per-host scoping. Document this
    clearly so the user knows what's captured (target tab + popups) vs not (everything else).
  - ADR-13's `launch_persistent_context` design is RETAINED as the fallback. ADR-14 adds
    CDP-attach as the PRIMARY. The build session reads ADR-14 (not ADR-13) for the
    authoritative implementation.
  - mitmproxy (`glyph capture proxy`) stays a FUTURE mode for Firefox/Safari or wire-level
    capture — NOT v1. The existing `glyph/capture/mitm.py` addon is the foundation; a
    `glyph capture proxy` CLI + WebSocket addon support + browser-proxy-config guidance is
    ~100-150 LOC, deferred (backlog).
  - The live capture path stays the SAME when `--browse` is NOT set — no regression to the
    existing headless auto-explore + dashboard-takeover flow.
- **Research backing:** `.context/memory/reviews/2026-07-31-browse-mode-research.md`
  section 7 (real-browser analysis). CDP-attach works for the user's Brave + Edge (both
  Chromium); gives the real daily session; no cert/QUIC/pinning friction; DOM works for
  Rosetta; decrypted bodies for free (browser does TLS). mitmproxy rejected for v1 (the
  user's browsers are Chromium → CDP-attach is strictly better; mitmproxy's cert-install +
  QUIC-disable + DOM-loss are unnecessary costs for them).
- **Supersedes:** ADR-13 (proposed, unimplemented). ADR-13's launch-persistent-context
  technique becomes the FALLBACK in ADR-14; ADR-14's CDP-attach is the PRIMARY. ADR-13 is
  kept for the research trail.

---
## ADR-15: Analysis stages run CONCURRENTLY as a parallel pipeline (2026-08-01)
- **Status:** proposed → **accepted/implemented this session (Session 24)**.
- **Context:** The user asked why the post-capture stages (schema, rosetta, sensitive,
  snihunt) wait for each other during `run`/`run live`. They largely DON'T need to. The
  real dependency graph: `schema -> rosetta` (rosetta's dom_attribute strategy reads the
  enum-candidate fields schema inference writes — must chain), while `sensitive` and
  `snihunt` are independent of both (sensitive scans flows directly; snihunt reads the
  captured host surface). snihunt is the SLOWEST stage (bounded network recon: DoH, CT
  logs, reverse-IP), yet historically ran last — after everything had finished.
- **Decision:**
  - New `glyph/pipeline.py::run_analysis(db_path, target=..., no_sensitive=...,
    no_snihunt=..., snihunt_no_net=..., progress=...)` runs THREE LANES concurrently over
    a ThreadPoolExecutor: lane 1 = schema→rosetta (chained), lane 2 = sensitive, lane 3
    = snihunt. Opt-out flags skip lanes. Result dict shape `{sch, ros, sens, sni}`
    unchanged, so the CLI renderers are untouched.
  - **Every lane opens its OWN Catalog connection and re-activates the target first**
    (`set_target(target)`). Two reasons: sqlite3 connections are bound to their creating
    thread (no cross-thread sharing), and a fresh Catalog has no active target — without
    set_target every write silently falls into the reserved `(unassigned)` bucket (id=0).
  - **This fixes a latent bug the parallelization forced into the open:** the TUI's
    analysis workers (`_analyze_once`/`_finalize`) opened a fresh Catalog WITHOUT
    set_target, so the live dashboard's fields/dictionary/findings landed in the
    (unassigned) bucket instead of the capture target. Session 23's on-device run proved
    it: `glyph target show example.com` reported findings 0 / fields 0 / dictionary 0
    while the dashboard displayed findings. run_analysis's per-lane set_target fixes it
    for both the TUI and the headless CLI (`glyph/cli/run.py::_gather` now delegates).
  - WAL + busy_timeout=5000 already support concurrent writers (built for the TUI's
    capture/analyze overlap, Session 15); findings writes are kind-scoped per stage
    (Session 16 fix) so concurrent sensitive + snihunt lanes never wipe each other.
  - Progress callbacks are lock-guarded in run_analysis so concurrent lane lines never
    interleave mid-print. A lane exception propagates after the pool drains.
- **Consequences:** wall-clock for `run har`/`run live` drops toward
  max(schema+rosetta, sensitive, snihunt) instead of the sum; the TUI's live ticks
  (schema+rosetta ∥ sensitive) and finalize (all three incl. snihunt) parallelize the
  same way; the (unassigned) bucket stops silently accumulating analysis rows.
- **Supersedes / amends:** nothing. Builds on ADR-10 (snihunt finalize-only in the TUI —
  unchanged: live ticks still skip the hunt), ADR-12 (multi-target — per-lane set_target
  keeps every write stamped with the active target_id).

---
## ADR-16: The current target is persisted and restored for display commands (2026-08-01)
- **Status:** accepted
- **Context:** Users reported that table outputs (flows, dictionary, sensitive, dashboard)
  fetched rows from ALL targets instead of only the current one. The store layer already
  filtered every read to the ACTIVE target — but the active target lived only in memory on
  each `Catalog` instance, so every display command that opened a fresh `Catalog` had no
  active target and reads silently fell back to all targets.
- **Decision:** Persist the current target as meta key `active_target_id` (written by
  `set_target`/`set_active_target`, cleared by `clear_active_target`/`set_active_target(None)`/
  `remove_target`). Add `Catalog(path, restore_active=True)` to restore it on open (refusing
  the reserved unassigned bucket id=0 and self-cleaning stale ids). Display + stage CLI
  commands, all TUI read sites, `pipeline._open()`, and the mitm addon opt in;
  run/capture write paths stay pristine (ADR-12 unchanged — they set their own target).
  `glyph target list` marks the current target; `glyph target show` persists the switch.
- **Consequences:** The reserved (unassigned) bucket (id=0) can never become the restored
  current target. `set_active_target(0)` is one-shot display only and never nukes a
  previously persisted real target. Passive mitm proxy traffic buckets under the persisted
  current target — use a per-target proxy run or a fresh catalog for the unassigned fallback.
  Future display commands must pass `restore_active=True` (via `_shared.catalog`) or they
  will read ALL targets' rows again.
