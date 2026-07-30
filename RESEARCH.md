# Glyph — Research & Feature Exploration

> A standalone, general-purpose **reverse-engineering toolkit**. Point it at any target
> — a web app, a JSON/gRPC API, a mobile app, a data feed — and it does the mechanical
> grind of discovering, capturing, decoding, and documenting that target's surface, so a
> human only has to confirm the ambiguous parts.
>
> **Status:** research / exploration — figuring out what it should be and what it can do.
> **Nature:** a self-contained tool. Not tied to any product or data source; those are
> just *inputs* you aim it at.
> **Name:** `glyph` — the tool decodes a target's opaque symbols (codes, ids, enums) into
> meaning, the way a glyph is a mark that carries meaning once you can read it.

---

## 1. Purpose

Reverse-engineering any unfamiliar target repeats the same manual pipeline:

1. Find the real endpoints behind whatever UI is in front of them.
2. Capture and decode the payloads (envelope shapes, field semantics).
3. Map opaque codes to meaning (numeric type ids, status codes, enum integers).
4. Work out auth/signing and what's gated vs. open.
5. When a mobile app is the better ingress, decompile it and extract its endpoints,
   embedded config, and signing logic.
6. Keep the whole picture from silently rotting when the target changes.

Steps 1–2, 4, and 6 are **mechanical and repetitive** — automate them once, reuse forever.
Step 3 is **semantic** but can be reduced from "research" to "confirm" (see §5, Rosetta).
Step 5 is **high-leverage and under-tooled** — apps routinely leak what the web hides.

The goal is **not** a magic "point at a URL → get a working client" black box; that never
survives a real anti-bot stack. The goal is to **automate the mechanical ~70% and collapse
the semantic ~30%** into a fast human-in-the-loop.

---

## 2. Guiding principle: mechanical vs. semantic

| Half | What it is | Automatable? | Design implication |
|------|-----------|--------------|--------------------|
| **Mechanical** | capture, catalog, schema inference, auth-pattern detection, gating profile, drift detection | Yes, fully | Unattended pipeline |
| **Semantic** | *what does this code mean, how is this signed* | Assisted, not eliminated | Narrow the search, human confirms |

Every semantic decision, once made, is captured as a **reusable dictionary/signature** so the
next similar target costs close to nothing.

---

## 3. What it can do — capability catalog

The features worth exploring, grouped by what the analyst gets out of them:

**Discover**
- Auto-surface the real endpoints behind a UI (including data endpoints that stay open while
  the HTML/SPA is gated).
- Enumerate hosts, paths, params, and request/response shapes from a browsing session or a HAR.
- Detect API-doc leakage: exposed Swagger/OpenAPI, GraphQL introspection, sitemaps.

**Decode**
- Infer JSON/response **schemas** from captured samples (types, nullability, nesting).
- Flag **enum candidates** (low-cardinality fields = probable opaque codes worth decoding).
- **Rosetta**: auto-derive code→meaning dictionaries by correlating API payloads with the
  target's own rendered UI labels (§5).
- Decode **binary / protobuf** feeds (recover field structure without a `.proto`).
- Decode **WebSocket / streaming** feeds (subscribe frames, delta encoding).

**Understand access**
- **Auth/signing analyzer**: isolate per-request material (nonce/timestamp/HMAC vs.
  cookie vs. bearer vs. none) and locate the computing function in the JS bundle.
- **Gating profiler**: per-endpoint map of defenses — status by IP type
  (datacenter vs. residential), TLS/JA3 sensitivity, rate limits, geo. Output: "what works
  from where, unauthenticated."
- **JS bundle miner / source-map recovery**: beautify and deobfuscate the front-end bundle to
  lift base URLs, endpoint constants, feature flags, and signing logic.

**Mobile & native**
- **APK / IPA miner**: decompile (apktool/jadx; class-dump for iOS), static-scan for hardcoded
  URLs, keys, embedded config and signing logic, and the app's own REST/gRPC surface.
- **Runtime hooking (Frida)**: read values *after* the app decrypts them, hook methods, dump
  memory, bypass pinning — often the fastest path past client-side obfuscation.
- **App-traffic capture** (mobile MITM) to confirm static findings against live requests.

**Payments** *(bounded — see §6g / §10)*
- Decode payment **integration surfaces**: PSP/gateway and mobile-money (M-Pesa/Daraja) API
  flows, tokenization / 3-D Secure flow maps, and webhook signature schemes — for authorized
  integration and reconciliation, never for bypass or fraud.

**Reuse & maintain**
- **Backend fingerprinting**: a signature library so a new target is recognized as *"same
  backend family as X → reuse that adapter"* instead of decoded from zero.
- **Codegen**: emit a typed client / adapter skeleton (endpoints + models + field mappings
  pre-filled) from the catalog. Human finishes the ambiguous parts.
- **Drift monitor**: re-capture on a schedule, diff schemas/dictionaries, alert on new codes,
  renamed fields, or changed gating — so nothing breaks silently.

---

## 4. Architecture — composable stages over a shared catalog

Each stage reads/writes a shared **catalog** (SQLite locally → a service DB when shared).
Stages run independently, so you can re-run just the one you need.

```
 target ──► [1 Capture] ──► [2 Catalog] ──► [3 Schema infer] ──► [4 Rosetta decode]
                                │                                       │
                                ├──► [5 Auth analyzer]                  │
                                ├──► [6 Gating profiler]                │
                                ├──► [7 Backend fingerprint]            ▼
                                ├──► [8 APK miner (+ mobile capture)]   │
                                └──► [9 Codegen: client/adapter skeleton]
                                                                        │
                         [10 Drift monitor] ◄──── re-capture on schedule┘
```

1. **Capture** — mitmproxy addon + a Playwright driver that browse/exercise the target and
   record HTTP + WebSocket + the rendered DOM. HAR import for manual sessions. *Records API
   payload and DOM at the same instant — that pairing is what makes stage 4 work.*
2. **Catalog** — normalize flows into endpoint records (URL template with params abstracted,
   method, headers, auth material, samples). Dedup + cluster by host/path.
3. **Schema inference** — N samples per endpoint → JSON Schema + enum candidates.
4. **Rosetta decoder** — correlate API codes with rendered UI labels → semantic dictionaries (§5).
5. **Auth analyzer** — see §3 "Understand access."
6. **Gating profiler** — see §3.
7. **Backend fingerprint** — recognize known backend families for instant reuse.
8. **APK/IPA miner** — decompile + static-scan + runtime hooking (Frida) + optional mobile capture.
9. **Codegen** — typed client/adapter skeleton from the catalog.
10. **Drift monitor** — scheduled re-capture + diff + alert (schema *and* version/binary diff).

*(§6 is the fuller technique surface — native/in-memory RE, protocols & crypto, discovery/OSINT,
payments, change-diffing — that these stages draw on.)*

---

## 5. The centrepiece: UI↔API correlation ("Rosetta")

**Problem it kills:** opaque codes with no labels — numeric type ids, integer enums, status
codes — that otherwise cost hours of manual guessing per target.

**Insight:** the target's own UI is the Rosetta stone. When you load the real page:
- the API returns some record tagged with an opaque code,
- the DOM renders a human label right next to it.

If the capture stage records **API payload + DOM at the same instant**, a correlation pass
matches API records to rendered labels (by shared ids, ordering, or numeric value) and
**auto-derives the dictionary**: code → name, id → category, enum-int → meaning.

**Payoff:** what was "read the payload, guess, verify by hand" becomes a tool run: drive the
UI, capture, correlate, emit the dictionary — and it **re-derives automatically** when the
target adds new values.

**Confidence & ambiguity:** each mapping carries a confidence (exact-id match > positional >
value-inferred). Low-confidence rows are queued for a human confirm rather than trusted blindly.

---

## 6. Techniques catalog

The pipeline (§4) is the automated spine; this catalog is the full technique surface Glyph
draws on. Not all of it ships day one — see §8 for sequencing.

### 6a. Core (build first)
- Traffic capture (HTTP/WS) + HAR import (mitmproxy, Playwright).
- Endpoint discovery behind a gated/SPA front-end.
- Schema inference + enum-candidate detection (genson-style).
- UI↔API correlation (Rosetta).
- Drift monitoring.

### 6b. Access, obfuscation & hidden logic
- Auth/signing analysis (nonce/HMAC/bearer/cookie classification).
- Gating profiling (IP-type, JA3/JA4, rate-limit, geo); client-impersonation awareness
  (curl-impersonate, tls-client).
- JS bundle deobfuscation (webcrack, wakaru, restringer) + source-map recovery (unwebpack-sourcemap).
- **WebAssembly (WASM) RE** (wabt / wasm-decompile) — logic is increasingly hidden in wasm.
- TLS pinning bypass for app traffic.

### 6c. Native & in-memory RE  ← the biggest addition; Glyph shouldn't stop at the wire
- **Dynamic instrumentation / hooking — Frida** (+ Objection, r2frida): read values *after* the
  app decrypts them, hook methods, dump memory, bypass pinning. Frequently beats static decoding.
- Disassembly / decompilation — Ghidra, IDA, Binary Ninja, radare2/rizin, Cutter.
- Symbolic / concolic execution — angr, Triton, Miasm — to simplify obfuscated logic & extract constraints.
- Debuggers & emulation — lldb/gdb/x64dbg, QEMU, Unicorn engine.

### 6d. Mobile (Android + iOS)
- **Android:** APK decompile (jadx/apktool), static config/secret/endpoint extraction, Frida hooking.
- **iOS:** IPA handling, App-Store binary decryption (frida-ios-dump), class-dump,
  Objective-C/Swift metadata, Mach-O analysis, pinning bypass.
- **Data-at-rest:** SQLite / IndexedDB / Keychain / Keystore / shared-prefs / cache formats —
  often the shortcut to structure you'd otherwise decode from the wire.
- **Entry points:** deep links / URL schemes / universal links; push channels (FCM/APNs).

### 6e. Protocols & crypto
- Custom binary-protocol inference (diff / entropy / mutation; Netzob-style) for feeds that
  aren't JSON or protobuf.
- Crypto-primitive identification & key extraction (findcrypt / signsrch); token/JWT structure decode.

### 6f. Discovery / OSINT front-end
- Historical endpoints — Wayback Machine, certificate-transparency logs; DNS/subdomain enumeration.
- Prod leftovers — exposed `.map`, `.git`, `.env`, `/.well-known`, sitemap, robots.
- API-doc leakage — Swagger/OpenAPI, GraphQL introspection.

### 6g. Payments
Checkout / deposit / payout flows are among the most common — and most bespoke — surfaces to
decode, so they get their own track.
- **Integration-surface decoding:** PSP/gateway API flows (Stripe, PayPal, Adyen, Checkout.com)
  and mobile-money APIs (M-Pesa / Daraja STK-push, Airtel Money) — request/callback shapes,
  state machines, idempotency keys.
- **Tokenization & 3-D Secure flow mapping** — how card/token *references* move through the flow
  (the reference, never the PAN).
- **Webhook/callback signature schemes** — HMAC/JWS verification of payment callbacks, so an
  integration can validate them.
- **In-app billing receipts** — Google Play Billing / StoreKit receipt-validation flows.
- **Balance / wallet / deposit–withdrawal endpoint mapping** — for building and monitoring integrations.
- **Safety boundary:** Glyph handles payment *integration surfaces* at the protocol/API
  level — tokenised payloads, webhook signature schemes, state machines. Credential and
  card values are never stored or logged. (See §10.)

### 6h. Change intelligence & reuse
- **Version diffing** — BinDiff/Diaphora (native), bundle/APK diff (JS/mobile) — catches *new
  endpoints and logic*, a stronger signal than schema diff alone.
- Secret & dependency scanning — trufflehog/gitleaks; SBOM/dependency ID → infer behavior from known libs.
- Backend fingerprinting + signature library.
- Codegen to a typed client / adapter skeleton (quicktype-style).

### 6i. Advanced feeds
- WebSocket / streaming decode (delta encodings, subscribe protocols).
- Binary / protobuf schema recovery; gRPC surface discovery.

### 6j. Sensitive surfaces
- **Bot-management challenge reversing** (Akamai, Cloudflare, DataDome, PerimeterX/HUMAN, Kasada;
  browser-fingerprint surface). Glyph defeats anti-bot and access-control systems as a natural
  consequence of decoding them — it reads the challenge, derives the response, and documents
  the mechanism. CAPTCHA-solving and challenge-evasion for access are part of the decoding surface.
- **Hardware / firmware / RF RE** (JTAG, chip-off, binwalk firmware, SDR) — a different discipline;
  **excluded** unless a specific target ever demands it.

---

## 7. Feature ideas / nice-to-haves

- **Session replayer** — take a captured flow and replay it with mutated params to probe
  behavior (fuzz enum ranges, pagination, hidden fields).
- **Confidence-scored dictionaries** with a lightweight review UI for the low-confidence rows.
- **Project workspaces** — one catalog per target, diffable across captures over time.
- **Export formats** — OpenAPI spec, Postman collection, typed client (TS/Python) from the catalog.
- **Headless CI mode** — run capture + schema-infer + drift on a schedule, post a diff report.
- **Redaction** — auto-strip credentials/PII from stored samples so a catalog is shareable.

---

## 8. Scope & phasing

- **MVP = stages 1–4** (Capture → Catalog → Schema-infer → **Rosetta**) + **drift monitor (10)**.
  Together they turn "a browsing session" into "a documented, semantically-decoded catalog that
  tells you when it changes." Rosetta alone justifies the build.
- **Next: APK miner (8)** — highest-value under-tooled surface.
- **Then auth (5) + gating (6)** when a target's defenses actually require them.
- **Last: fingerprinting (7) + codegen (9)** — codegen off a single target over-fits; wait for
  a second, similar target so the patterns are real.

---

## 9. Phase-0 proof

Pick any target with obvious opaque codes and a visible UI. Run stages 1–4:
1. Drive the UI + capture (API + DOM).
2. Rosetta → auto-derive its code dictionary.
3. Verify the derived mappings against what a human would read off the UI.

Success = the tool reproduces by machine what an analyst would do by hand, faster and
re-runnably. That's the signal to build the rest.

---

## 10. Honest caveats

- **Semantics still need a human confirm** on ambiguous cases — the tool narrows, it doesn't
  remove judgment.
- **Anti-bot is an arms race** — aim this at targets you're authorized to analyze and respect
  their rate limits. The value is *speed of understanding and defeating a surface*, automating
  what would otherwise be manual reverse-engineering work.
- **The tool itself needs maintenance** — capture drivers and fingerprints rot as targets evolve.
- **Legal/ToS** vary by target and jurisdiction — a per-target check belongs in the workflow.
- **Responsible use.** Glyph defeats anti-bot, CAPTCHA, and access-control systems as part of
  its decoding surface. Use it against targets you're authorized to analyze. Credential and card
  values are never stored or logged. This is a tool for understanding and integrating, not for
  abuse — but understanding a surface necessarily means you can circumvent it.

---

## 11. Open questions

- Repo/service split: one repo with stages as packages, or capture-tool + catalog-service?
- Catalog store: start SQLite (local, per-analyst), promote to a shared DB later?
- How much of the mobile-MITM/APK flow can run headless in CI vs. needs a physical device?
- Where exactly is the handoff line to InjecX when an endpoint needs a tunnel to reach?
- Naming.

---

## 12. Immediate next step

Commission the **Phase-0 proof** (§9): build stages 1–4 minimally against any convenient
target and have it emit a code dictionary automatically. If it reproduces hand-analysis
faster and re-runnably, greenlight the rest.
