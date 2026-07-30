# Glyph — Deep-Dive Research Companion

> **Status:** research companion to [RESEARCH.md](RESEARCH.md). Where RESEARCH.md is the *canon* (scope, technique catalog, architecture, phasing — the original 305-line thesis), this document is the *pressure-test*: every claim in RESEARCH.md checked against real online research (2025–2026 sources), every named tool verified for current version + license + maintenance, the centerpiece (Rosetta) checked for prior art, the competitive landscape mapped, and the open questions resolved with concrete recommendations.
>
> **Authored:** 2026-07-30, Session 3 (Super Z / glm-5.2). Built on RESEARCH.md + ADR-1 + five parallel online-research clusters (capture+schema+codegen, Rosetta prior art, mobile+native+JS RE, sensitive surfaces, competitive landscape). Raw research notes archived under `.context/memory/reviews/` and `/home/z/my-project/tool-results/`.
>
> **How to read:** section numbers mirror RESEARCH.md where applicable (§4, §5, §6a–§6j, §8, §9, §10, §11). Each section opens with a one-line **verdict** so you can skim; the body explains. Anything marked **could not verify online** is honest about the gap.

---

## 1. Executive Summary

Glyph's thesis holds up. The mechanical-vs-semantic split (RESEARCH.md §2) is the right framing: the mechanical ~70% (capture, catalog, schema inference, gating profile, drift) is fully automatable today with mature OSS building blocks, and the semantic ~30% collapses into a fast human-in-the-loop when you pair API payloads with rendered DOM at capture time (the Rosetta insight, §5). The composable-stages architecture (§4) is sound — each stage maps to a real, maintainable tool.

Three substantive findings change the picture from RESEARCH.md:

1. **Rosetta is genuinely novel — as a combination.** Every individual half exists in mature form (Playwright Trace Viewer gives you API+DOM pairing for free; genson infers schemas; Fellegi-Sunter scores record linkage; Label Studio handles HITL review). But no published tool or paper derives code→meaning dictionaries by treating the rendered UI as semantic ground truth. The single closest published work — *Carving UI Tests to Generate API Tests and API Specification* (Yandrapally et al., ICSE 2023) — drives the UI, captures XHR/fetch, and emits OpenAPI specs, but stops at *structure*. Glyph's Rosetta sits precisely in the gap between what that paper captures and what a human analyst does by eyeballing the page. **Recommended positioning pivot:** don't claim "novel capture technique"; claim "semantic decoding layer over Playwright-Trace-Viewer-style paired captures, using Fellegi-Sunter-class confidence scoring and Label-Studio-class HITL review."

2. **The APK miner (RESEARCH.md §6d, stage 8) is greenfield — and the building blocks are all permissively licensed.** No existing OSS tool emits a Glyph-style endpoint catalog + signing-logic extraction from an APK. MobSF (21.2k★, GPL-3.0) is the nearest neighbor but stops at security scoring; its REST API and manifest parser are reusable as a *subprocess* (the GPL blocks embedding). The Android stack — apktool (Apache) + jadx (Apache) + apk-mitm (MIT) + Frida (GPLv2+commercial — drive as subprocess) — is fully headless and CI-friendly. iOS is the constraint: it needs a jailbroken device, no fully-headless path exists.

3. **The competitive landscape has three close neighbors, none of which do what Glyph does.** Akto (OSS, MIT) is closest on the capture→catalog→schema half but stops there. Levo.ai (commercial, eBPF) is closest commercially but only sees your *own* traffic — Glyph drives an external target's UI. MobSF is closest on the APK-miner half but stops at security findings. No published tool combines traffic capture + schema inference + codegen + Rosetta-style semantic decoding + mobile RE + drift. **Two novelty risks to monitor:** Salt Security's opaque "business-logic learning" ML (could be doing something Rosetta-like internally — demo before claiming total novelty), and Cloudflare's ML API Discovery + Schema Learning (Mar 2023 — the cleanest published production example of the discovery+schema half, cite defensively).

A fourth, Kenya-specific finding: **M-Pesa Daraja does not sign its callbacks** — anyone with the CallBackURL can POST a fake payment notification. This is a known integration hazard and a first-class opportunity for Glyph to ship a "Daraja callback verification" recipe (out-of-band STK-query + idempotent short-code matching) as part of §6g.

---

## 2. Scope corrections since RESEARCH.md was written

RESEARCH.md was written 2026-07-29 and amended by two follow-up commits (`b66053f`, `62b06ae`) that reframe Glyph's posture on sensitive surfaces. The original "Out of scope" section was replaced with a "defeats as a natural consequence of decoding" framing (ADR-1, latest text):

> *"Glyph defeats anti-bot, CAPTCHA, and access-control systems as a natural consequence of decoding them; it decodes payment-integration surfaces at the protocol/API level (tokenised payloads, not raw card values). Credential and card values are never stored or logged."*

This deep-dive treats that framing as authoritative. The implication for the technique catalog: bot-management and CAPTCHA mechanisms (§6j) are in-scope as *decoding surfaces* — Glyph reads the served challenge JS, derives the expected response format, and emits a documented mechanism record into the catalog. They are not in-scope as *attack vectors* — Glyph does not ship solvers, does not bypass protections on targets it doesn't own, and requires per-target legal review (RESEARCH.md §10) before any of this surfaces in a non-research build. Payments (§6g) are in-scope at the protocol level only (tokenized payloads, webhook signatures, state machines); raw card/credential values are never handled.

---

## 3. Pressure-testing the technique catalog (RESEARCH.md §6)

For each sub-section of RESEARCH.md §6, this deep-dive records: **verdict** (holds / holds with caveats / needs revision), the concrete tools verified online, and the integration recommendation. Full tool-by-tool detail (versions, licenses, API surfaces, last-release dates) is in the cluster research notes — this section is the synthesis.

### 3a. Core (RESEARCH.md §6a) — **holds, validated**

RESEARCH.md names: traffic capture (mitmproxy, Playwright) + HAR import; endpoint discovery behind SPA front-end; schema inference + enum-candidate detection (genson-style); UI↔API correlation (Rosetta); drift monitoring.

**Verified:**
- **mitmproxy v12.2.3 (May 2025), MIT.** Python addon API with event hooks (`request`, `response`, `websocket_message`, `tls_clienthello`, `tls_connected_client`, `load`, `done`). Built-in HAR export since v10.1 (Sep 2023). HTTP/1, HTTP/2, HTTP/3, WebSockets, arbitrary SSL/TLS. Known gap: plaintext gRPC (h2c over TCP without TLS) is not fully supported (issue #6998). Glyph drives it as `DumpMaster` in-process or `mitmdump -s addon.py` as subprocess. https://docs.mitmproxy.org/stable/api/events.html
- **Playwright v1.48+ (Oct 2024), Apache-2.0.** `page.routeWebSocket()` (since v1.48) intercepts WS in-page. Native HAR export via `record_har_path` + `record_har_content="embed"`. `--tracing on` produces a `trace.zip` with screenshots, DOM snapshots, network waterfall — **this is the API+DOM pairing data Rosetta needs, for free.** Proxy integration: `browser.launch(proxy={"server": "http://localhost:8080"})` feeds all browser traffic through mitmproxy. https://playwright.dev/docs/trace-viewer
- **HAR 1.2 (frozen since 2012).** W3C Web Performance WG abandoned formal standardization. **Critical limitation:** HAR 1.2 has no WebSocket message bodies — only the upgrade handshake. Chrome DevTools exports a non-standard `_webSocketMessages` array; Playwright HAR omits WS entirely. **Glyph takeaway:** treat HAR as the import/export interchange for HTTP req/res only; store WS and binary streams as native `.mitm` flows or custom JSONL.
- **genson v1.4.0, MIT, Python ≥3.10.** `Builder().add_object(json).to_schema()` — incremental schema merging across many samples (so Glyph can stream). Emits Draft-04 through 2020-12. Configurable enum/optional inference. Rust port `genson-rs` for speed.
- **quicktype v23.2.0, Apache-2.0.** JSON samples → typed models in 15+ languages (TS, Python, Go, Rust, C#, Swift, Java, Kotlin, etc.). Detects low-cardinality string fields as unions of literals. No first-class Python library — Glyph shells out or calls the JS API over IPC.
- **oasdiff, Apache-2.0, Go lib + CLI + GitHub Action.** Compares two OpenAPI specs, classifies each change as breaking/non-breaking, detects 506 distinct change types. **This is Glyph's drift-monitor engine.** Glyph re-captures on schedule → regenerates OpenAPI from inferred schemas → runs `oasdiff` → alerts on breaking changes and new enum values. https://www.oasdiff.com
- **Optic — ARCHIVED 2026-01-12.** Do not depend on. Industry consensus: migrate to oasdiff.

**Recommendation:** MVP stages 1–4 (Capture → Catalog → Schema-infer → Rosetta) + drift monitor (stage 10) all have mature, permissively-licensed building blocks. The integration work is real but the foundations are solid.

### 3b. Access, obfuscation & hidden logic (RESEARCH.md §6b) — **holds, with JA4 + curl-impersonate added**

RESEARCH.md names: auth/signing analysis (nonce/HMAC/bearer/cookie); gating profiling (IP-type, JA3/JA4, rate-limit, geo); client-impersonation awareness (curl-impersonate, tls-client); JS bundle deobfuscation (webcrack, wakaru, restringer) + source-map recovery (unwebpack-sourcemap); WASM RE (wabt, wasm-decompile); TLS pinning bypass.

**Verified:**
- **TLS fingerprinting has standardized on JA4/JA4+ (FoxIO, 2023).** Cloudflare rolled it out enterprise-wide Aug 2024. JA4 leaves the ClientHello fields unhashed (human-readable, unlike JA3's MD5); JA4H adds HTTP/2 SETTINGS + header order; JA4S (server), JA4X (X.509), JA4SSH extend the family. https://github.com/FoxIO-LLC/ja4
- **Client-impersonation stack:** `lwthiker/curl-impersonate` (fork of curl + BoringSSL patched to emit Chrome/Edge/Safari/Firefox ClientHello + HTTP/2 framings); `bogdanfinn/tls-client` (Go-backed, Python bindings); `curl_cffi` (Python, drop-in `requests`-like API). All actively maintained. https://github.com/lwthiker/curl-impersonate
- **JS deobf stack (verified order):**
  1. `unwebpack-sourcemap` — short-circuit if a `.map` exists. Original `rarecoil/unwebpack-sourcemap` archived Apr 2022; live Python fork `orsinium-labs/sourcemap` on PyPI (Jan 2023). Source-map recovery is dramatically better than bundle deobfuscation.
  2. `webcrack` v2.16.0 (~Apr 2025), MIT, Node 22+. `import { webcrack } from 'webcrack'; await webcrack(code)` returns an unpacked module tree. Deobfuscates obfuscator.io output, unminifies, unpacks webpack/browserify.
  3. `wakaru` v1.2.0 — JS decompiler for modern frontend. Unpacks webpack/esbuild/Rollup/Vite, reverses minifier+transpiler output to modern ESM. Complementary to webcrack — run after to split cleaned bundle into per-module ESM matching original layout (layout = strong signal for the auth/signing analyzer).
  4. `restringer` (HumanSecurity, Aug 2022 — *not* ChatGPT-era, pre-LLM) — pattern-driven deobfuscator. Obfuscation Detector classifies the obfuscation type from AST structure, then applies targeted techniques (string-array reconstruction, control-flow unflattening, proxy inlining). Third pass to catch obfuscator-specific patterns webcrack/wakaru miss.
  - **Legacy to skip:** de4js (v1.12.0, Dec 2021, unmaintained) and JSNice (ETH 2014, statistical renaming — useful only as a final rename pass).
- **WASM RE is immature in 2025.** `wabt` (BSD-like) + `wasm-decompile` + `wasm2c` + `ghidra-wasm-plugin` (nneonneo, active) give text/C output, but **no production tool reverses obfuscator-style WASM control-flow flattening.** Best practical path: `wasm2c` → Ghidra (+ wasm plugin) → angr. Research: LLVM-based de-obfuscator (RE//verse 2025 talk); `WaDec` (arXiv 2406.11346) is academic LLM-only. **Flag as an open research problem** — WASM-based logic hiding is a growing attack surface Glyph can document but not fully decode.

**Recommendation:** the §6b surface is mature. Glyph's auth/signing analyzer should locate the computing function in the (deobfuscated) JS bundle, extract the algorithm, and emit a reference implementation. For gating profiling, JA4 + JA4H are the current standard — RESEARCH.md's mention of "JA3/JA4" should be updated to "JA4/JA4+ (JA3 retained for backward compat)."

### 3c. Native & in-memory RE (RESEARCH.md §6c) — **holds, Frida is the keystone**

RESEARCH.md names: Frida (+ Objection, r2frida); disassembly/decompilation (Ghidra, IDA, Binary Ninja, radare2/rizin, Cutter); symbolic/concolic execution (angr, Triton, Miasm); debuggers & emulation (lldb/gdb/x64dbg, QEMU, Unicorn).

**Verified:**
- **Frida v17.16.4 (Jul 21 2025), GPLv2 + commercial exception.** Inject JS into a running process on Windows/macOS/Linux/iOS/Android; hook arbitrary functions, read/write memory, trace, dump decrypted buffers, bypass TLS pinning. Python bindings: `import frida; session = frida.attach(pid); script = session.create_script(js)`. **License constraint:** Glyph must drive `frida-server` as a **subprocess** (standard usage) — that keeps Glyph out of GPL territory. Linking libfrida-core would force GPL on the combined work. 17.0.0 (May 17 2025) added Android 16 + breaking API changes (`Module.getExportByName` → `Module.getGlobalExportByName` / per-module `findExportByName`). Codeshare scripts cover pinning bypass: `@Q0120S/bypass-ssl-pinning`, `@pcipolloni/universal-android-ssl-pinning-bypass-with-frida`.
- **Objection** (sensepost, BSD historically) — Frida-based runtime mobile exploration. Pre-built commands: SSL pinning bypass, keychain dump, file-system inspection, method hooking. Works on non-jailbroken iOS / non-rooted Android via `objection patchapk`/`patchipa` (embeds `frida-gadget`). **For human-REPL phase only** — prefer hand-written Frida scripts for headless CI.
- **r2frida** (LGPL-3.0) — radare2 IO plugin that ships Frida. Drive Frida from r2's command language. Merges static (r2) and dynamic (Frida). `r2pipe` for scripting.
- **Disassemblers/decompilers — license + headless matrix:**

  | Tool | Version | License | Headless API |
  |------|---------|---------|--------------|
  | **Ghidra** (NSA) | 11.4.3 (Dec 2025) | Apache-2.0 | `AnalyzeHeadless` + Java/Jython/JS |
  | **IDA Pro** | 9.2 | commercial | IDAPython, IDC, C++ SDK |
  | **Binary Ninja** | current | commercial (API MIT, app closed) | C++/Python/Rust; headless only on Commercial/Ultimate |
  | **radare2/rizin + Cutter** | active | GPLv3 / LGPL-3.0 | `r2pipe` — `cmd(str)` returns text or JSON (`cmdj`) |
  | **Capstone** | 5.0.9 (May 2026) | BSD-3 | C lib + bindings |

  **Ghidra is the OSS default.** `AnalyzeHeadless` runs headless; decompiler output accessible via `DecompInterface` from a `postScript`. Glyph subprocess-emits a JSON of function signatures + decompiled bodies. **radare2 + r2pipe is the lightest option:** `r2pipe.open(bin).cmd('aaa; pdf @ main')` returns disassembly text; `cmdj` returns JSON. **Capstone is a library, not a decompiler** — used by angr, Frida, Miasm, Binary Ninja under the hood. Glyph uses Capstone directly when it needs to walk instruction streams without launching a full decompiler.

- **Symbolic/concolic execution:**
  - **angr** (BSD-style) — most popular, Python 3.10+, CFG recovery, symbolic exec, Z3 constraint solving. `proj.factory.simulation_manager().explore(find=, avoid=)` then `state.posix.dumps(0)`.
  - **Triton** (Apache-2.0) — Dynamic Symbolic Execution library, taint engine, AST-based IR, C++/Python bindings. v0.8 added ARM32.
  - **Miasm** (CEA, **GPLv2**) — license flag. Older (2007/2011).
  - **Glyph: library (Python).** When the auth/signing analyzer localizes a signing function, hand the function's binary range to angr/Triton to recover input→output as a symbolic constraint, then emit a reference implementation. **Prefer angr or Triton** if Glyph wants to stay GPL-free.

- **Emulation:** QEMU v10.2 (Dec 2025, GPLv2) for full-system; Unicorn v2.0.0 (Oct 2021, GPLv2) for in-process CPU-only emulation (forked from QEMU, used by angr and Frida's Stalker). **Glyph: library.** Unicorn in-process for function-level (run a decryptor stub against captured ciphertext); QEMU for full-system. Frida wins for ground-truth runtime values; emulation wins for intermediate state Frida can't see (CPU flags) or code that won't load in a real process (anti-debug checks).

**Recommendation:** the §6c surface is mature. Glyph's native RE pipeline: locate signing function (Frida hook or Ghidra decompile) → recover algorithm (angr/Triton symbolic exec) → emit reference implementation. All key tools are scriptable; the only license flag is Miasm (prefer angr/Triton).

### 3d. Mobile (RESEARCH.md §6d) — **holds; Android is CI-friendly, iOS needs a jailbroken device**

RESEARCH.md names: Android (jadx, apktool, Frida hooking, static config/secret/endpoint extraction); iOS (IPA handling, frida-ios-dump, class-dump, Obj-C/Swift metadata, Mach-O analysis, pinning bypass); data-at-rest (SQLite, IndexedDB, Keychain, Keystore, shared-prefs, cache); entry points (deep links, URL schemes, universal links, push channels).

**Verified — Android (fully headless, permissively licensed):**
- **jadx** (skylot, Apache-2.0, Java 11+, Maven Central) — Dex→Java decompiler. CLI `jadx -d out/ app.apk`; programmatic via `JadxDecompiler` Java API; **JADXecute** plugin runs dynamic Java against the GUI's class model. Actively maintained.
- **apktool** v2.9.3 / 2.10.0 branch (iBotPeaches, Apache-2.0) — decodes `AndroidManifest.xml` + resources to nearly original form, disassembles dex to **smali**, rebuilds APKs. CLI `apktool d app.apk`. Glyph subprocess for manifest extraction (entry points, permissions) + resource decoding.
- **apk-mitm** (MIT) — one-shot CLI: decodes APK, patches Network Security Config, disables common pinning, rebuilds, signs, optionally launches mitmproxy. `apk-mitm app.apk`; `--proxy` for end-to-end. **Glyph subprocess for traffic-capture prep.**
- **Frida + Objection on Android** — rooted device + `frida-server`, or `objection patchapk` / `frida-gadget` injection for non-rooted. Android 16 supported in Frida 17.1.4 (Jun 2025).
- **Magisk + LSPosed** (GPLv3, license flag — device-side component only) — Zygisk injects into Zygote; LSPosed provides ART hooking. Stealthier than Frida against apps that detect Frida. Out of scope for MVP.

**Verified — iOS (requires jailbroken device, no fully-headless path):**
- **IPA decryption:** App Store binaries are FairPlay-encrypted; need a jailbroken device. `frida-ios-dump-ng` (Frida 17+, metadata analysis, IPA comparison) is current recommended; classic `frida-ios-dump` tested through iOS ~16; `frida-ipa-extract` (newer, supports App Store + sideloaded + system apps); **bagbak is deprecated** ("approach no longer recommended"). All require a jailbroken device.
- **class-dump (Obj-C metadata):** classic `class-dump` (nygard); modern `dsdump` (DerekSelander, Obj-C + Swift, activity Dec 2025); **iCDump** (romainthomas, LIEF author — cross-platform, no Mac needed, C++/Python). **iCDump is most CI-friendly.** Glyph: subprocess. `class-dump -H decrypted.app -o headers/` → scan headers for class/method names hinting at signing functions.
- **SwiftDemangle:** `swift-demangle` ships with the Swift toolchain; `swift-demangle.wasm` (kateinoigakukun) runs in browser/Node; `SwiftDemangle` (oozoofrog, Swift package, compatible through Swift 6.0/6.1, Feb 2026 active). Glyph: library — pipe every Swift symbol from class-dump through a demangler before pattern-matching.
- **Mach-O tools:** LIEF (Apache-2.0, Python/C++ APIs, parses Mach-O/PE/ELF cross-platform) — prefer over Apple-only `otool`/`install_name_tool` for CI portability. rizin's `rabin2` also parses Mach-O and emits JSON.
- **iOS pinning bypass:** Frida scripts (codeshare `@Q0120S/bypass-ssl-pinning`); Objection `ios sslpinning disable`. Native Swift pinning may require hooking `URLSessionDelegate` or lower-level `Network.framework`.

**Verified — data-at-rest:**

| Format | Where | Tool | License |
|--------|-------|------|---------|
| SQLite (plain) | both | `sqlite3` CLI / Python `sqlite3` (built-in) | public domain |
| **SQLCipher** (encrypted) | Android (local creds/tokens) | sqlcipher — 256-bit AES | **GPLv2 / commercial** — use CLI as subprocess. Recover key via Frida hook on `sqlite3_key`. |
| IndexedDB / LocalStorage / WebSQL | in-app WebViews | SQLite for WebSQL; leveldb for IndexedDB | — |
| iOS Keychain | iOS | **keychain-dumper** (ptoomey3, jailbroken) or Frida hooks on `SecItemCopyMatching` | MIT |
| Android Keystore | Android | Hardware-backed — cannot export private keys. Hook `KeyStore.getInstance` / `Cipher.init` with Frida to capture use. | — |
| Shared Preferences | Android | XML in `/data/data/<pkg>/shared_prefs/` — `adb pull` (root) or Frida file-system API | — |
| plist (iOS) | app container | `plutil` (Apple), Python `plistlib`, `plistutil` (libimobiledevice) | — |

**Verified — entry points (deep links / URL schemes / universal links / push channels):**
- **Android:** declared in `AndroidManifest.xml` (apktool output). Parse for `<intent-filter>` with `android.intent.action.VIEW` → scheme/host/pathPrefix (deep links / app links); `android:autoVerify="true"` for App Links; `MAIN`/`LAUNCHER` for launcher entry; `SERVICE`/`RECEIVER` for FCM (`FirebaseMessagingService` subclasses). FCM server key may be in `google-services.json` (sometimes in `assets/`) or `strings.xml`.
- **iOS:** declared in `Info.plist`: `CFBundleURLTypes` (URL schemes), `Associated Domains` entitlement (`applinks:`), `UIBackgroundModes` (`remote-notification` for push). APNs cert isn't in the IPA — only the entitlement and signing identity.
- **MASTG reference:** https://mas.owasp.org/MASTG-TEST-0028.
- **Glyph: static pass** over apktool output (Android) and `Info.plist` (iOS) → enumerate every entry point as catalog entries. **High-signal and under-tooled today.**

**Recommendation:** Android RE is fully headless/CI-friendly with permissively-licensed tools — Glyph's APK miner (stage 8) should ship Android support first. iOS support requires documenting the "jailbroken device required" constraint explicitly; the iOS pipeline is for analysts with hardware, not for CI. The APK miner as a service is **greenfield** — confirmed by both Task 5 and Task 7. MobSF is the nearest neighbor (REST API, URL/secret extraction) but stops at security scoring; borrow its manifest-parsing approach but emit a Glyph catalog entry (URL, signature scheme, decrypted-config blob) instead of a security score.

### 3e. Protocols & crypto (RESEARCH.md §6e) — **holds**

RESEARCH.md names: custom binary-protocol inference (Netzob-style); crypto-primitive identification (findcrypt, signsrch); token/JWT structure decode.

**Not re-verified in this deep-dive** (cluster 5 focused on JS/native/mobile RE, not protocol inference). The named tools (Netzob, findcrypt, signsrch) are mature research-grade; RESEARCH.md's framing is correct. **Gap to flag:** custom binary-protocol inference is a long tail — each bespoke protocol is its own decoding problem. Glyph should treat it as a "stage 4 extension" (after Rosetta handles JSON), not a day-one MVP feature. JWT decode is trivial (base64 + JSON parse + signature verify); ship it as a utility.

### 3f. Discovery / OSINT (RESEARCH.md §6f) — **holds**

RESEARCH.md names: Wayback Machine, certificate-transparency logs, DNS/subdomain enumeration; prod leftovers (`.map`, `.git`, `.env`, `/.well-known`, sitemap, robots); API-doc leakage (Swagger/OpenAPI, GraphQL introspection).

**Not re-verified in this deep-dive.** The named techniques are standard OSINT. **Concrete tools Glyph should wrap:**
- Wayback: `waybackpy` (Python) or the Wayback CDX API directly.
- CT logs: `censys` (Python) or `crt.sh` HTTP API.
- Subdomain enumeration: `amass` (OWASP), `subfinder` (ProjectDiscovery).
- Prod leftovers: a simple HTTP scanner (Glyph can build this in-house — it's a checklist of well-known paths).
- API-doc leakage: probe `/swagger.json`, `/openapi.json`, `/api-docs`, GraphQL `/graphql?query={__schema{types{name}}}`.

**Recommendation:** the OSINT front-end is straightforward; ship it as a stage-0 "pre-capture" pass that enriches the target's host inventory before mitmproxy+Playwright start driving.

### 3g. Payments (RESEARCH.md §6g) — **holds; Daraja callback gap is a first-class opportunity**

RESEARCH.md names: PSP/gateway API flows (Stripe, PayPal, Adyen, Checkout.com) + mobile-money (M-Pesa/Daraja STK-push, Airtel Money); tokenization & 3DS flow mapping; webhook/callback signature schemes; in-app billing receipts (Google Play Billing, StoreKit); balance/wallet/deposit-withdrawal mapping.

**Verified — webhook signature taxonomy (a clean Glyph dictionary candidate):**

| Provider | Webhook signature scheme | Idempotency | 3DS / SCA |
|----------|--------------------------|-------------|-----------|
| **Stripe** | `Stripe-Signature: t=<ts>,v1=<HMAC-SHA256>` — symmetric shared secret, 5-min replay tolerance | `Idempotency-Key` header | Inside PaymentIntent (`requires_action` → `next_action.use_stripe_sdk`) |
| **PayPal** | Asymmetric cert-fetch: `PAYPAL-CERT-URL` header → fetch X.509 → verify sig over `<transmission_id>\|<time>\|<webhook_id>\|<crc32(body)>` | `PayPal-Request-Id` header | `payment_source.card.attributes.verification.method` (`SCA_WHEN_REQUIRED`/`SCA_ALWAYS`) |
| **Braintree** | `bt_signature` (`public_key\|signature`) + `bt_payload` — signed form-urlencoded | (per-transaction) | via Braintree SDK |
| **Adyen** | HMAC-SHA256 in `additionalData.hmacSign` (standard) or header (non-standard); Base64 | `Idempotency-Key` header | `/payments` → `action.type = threeDS2` → `/payments/details` |
| **Checkout.com** | HMAC-SHA256 in `cko-signature` header over raw body | `Idempotency-Key` header | `3ds` object in payment request → `_links.redirect` |
| **Apple StoreKit 2** | **JWS chain** — every transaction is a signed JWS; validate against Apple root CAs | `transactionId` | (Apple handles) |
| **Google Play RTDN** | **No per-message signature** — IAM-governed Pub/Sub topic (Play is the only publisher) | `purchaseToken` | (Google handles) |
| **M-Pesa Daraja** | **NO SIGNATURE** — anyone with CallBackURL can POST a fake callback | None (dedup on `CheckoutRequestID`/`MpesaReceiptNumber`) | N/A (mobile money) |
| **Airtel Money** | Could not verify online — treat as untrusted | (per-transaction `id`) | N/A |
| **T-Kash** | Could not verify — no public developer portal found | — | N/A |

**Critical finding — M-Pesa Daraja (Kenya priority):** Daraja does **not** sign its callbacks. Multiple primary sources confirm (isaacmbira.com Jun 2026: *"Safaricom's Daraja API calls your callback URL when an STK Push completes, but it sends no signature and cannot set auth headers"*; de4sec.technology: *"Many integrations simply trust this callback — if it arrives at the right URL, the system marks the order as paid"*; LinkedIn/Kelvin Kibugi: *"The successful payment notification cannot be verified to have come from Safaricom, anyone with url can do a POST Request."*). The `CallBackURL` is an HTTPS POST endpoint you register; Safaricom POSTs JSON with `Body.stkCallback.CallbackMetadata` (amount, MpesaReceiptNumber, PhoneNumber) and `ResultCode` (0 = success; 1032 = cancelled; 1037 = timeout). URL keywords like `mpesa` in the callback path are rejected. **Verification must be out-of-band:** re-query via `/mpesa/stkpushquery/v1/query` with the `CheckoutRequestID`, or use the Transaction Status API.

**Recommendation:** ship a first-class "Daraja callback verification" recipe as part of §6g — out-of-band STK-query + idempotent short-code matching on `CheckoutRequestID`/`MpesaReceiptNumber`. This is a known integration hazard in the Kenyan ecosystem and a concrete differentiator. For the PSPs (Stripe/Adyen/Checkout.com/PayPal), document the HMAC/cert-fetch recipes and the idempotency-key contracts. For in-app billing, document the JWS-chain (Apple) and IAM-Pub/Sub (Google) delivery models. **Safety boundary reaffirmed:** no research touches raw PANs/CVVs or bypass techniques; every documented flow treats card data as opaque tokens.

### 3h. Change intelligence & reuse (RESEARCH.md §6h) — **holds; Optic is dead, use oasdiff**

RESEARCH.md names: version diffing (BinDiff/Diaphora native, bundle/APK diff JS/mobile); secret & dependency scanning (trufflehog/gitleaks, SBOM); backend fingerprinting + signature library; codegen (quicktype-style).

**Verified:**
- **oasdiff** (Apache-2.0, Go lib + CLI + GitHub Action) is the drift-monitor engine — see §3a. Originated at Tufin, now oasdiff org. Active. Side-by-side PR review. https://www.oasdiff.com
- **Optic — ARCHIVED 2026-01-12.** Was YC-backed OpenAPI diff/lint/test. Migration guides now point to oasdiff and APInotes. **Do not depend on Optic.**
- **openapi-diff** (OpenAPITools, Apache-2.0, Java/Maven) — alternative if a JVM toolchain is in use; less actively developed than oasdiff; simpler change taxonomy.
- **Native version diffing:** BinDiff (Google, zlib license) and Diaphora (GPLv2, license flag) are the standard Ghidra/IDA plugins for binary diffing — catches new endpoints and logic, a stronger signal than schema diff alone.
- **Secret & dependency scanning:** `trufflehog` (Apache-2.0) and `gitleaks` (MIT) are the standard scanners. Both scan git history and working tree. SBOM generation: `syft` (Apache-2.0).
- **Backend fingerprinting:** no off-the-shelf library — this is Glyph's signature-library work. Wappalyzer (MIT) covers web-tech fingerprinting; Shodan/Censys cover host-level. A "backend family" library (recognize "this is the same backend as X") is greenfield.
- **Codegen:** openapi-generator v7.24.0 (Sep 28 2025, Apache-2.0, 50+ generators) for spec→client; quicktype v23.2.0 (Apache-2.0) for raw-JSON→typed-model when an OpenAPI wrap is overkill. **No existing tool does raw-capture → typed-client end-to-end** — Glyph's combination would be novel.

**Recommendation:** drift monitor wraps oasdiff. Native diffing uses BinDiff (zlib, license-clean). Secret scanning wraps gitleaks (MIT). Backend fingerprinting is Glyph's signature-library work — start with a Wappalyzer-style tech fingerprint and extend with API-shape signatures.

### 3i. Advanced feeds (RESEARCH.md §6i) — **holds, with the HAR caveat**

RESEARCH.md names: WebSocket/streaming decode (delta encodings, subscribe protocols); binary/protobuf schema recovery; gRPC surface discovery.

**Verified:**
- **WebSocket capture:** mitmproxy captures WS frames as `WebSocketMessage` objects on the flow (accessible from the `websocket_message` addon hook). Playwright's `page.routeWebSocket()` (v1.48+, Oct 2024) intercepts WS in-page but **HAR 1.2 cannot store WS message bodies** — only the upgrade handshake. Chrome DevTools exports a non-standard `_webSocketMessages` array; Playwright HAR omits WS entirely. **Glyph takeaway:** store WS frames in the catalog as native JSONL, not in HAR.
- **gRPC / protobuf:** mitmproxy supports gRPC via the HTTP/2 layer; v12's interactive contentviews parse and re-encode protobuf/msgpack. **Known gap:** plaintext gRPC (h2c over TCP without TLS) is not fully supported (issue #6998). For protobuf schema recovery without a `.proto`, `protoc --decode_raw` gives field numbers + wire types; `protobuf-inspector` (Python) gives a tree view. No production tool recovers a full `.proto` from raw protobuf traffic — research-grade only.
- **SSE (Server-Sent Events):** straightforward — `text/event-stream` parsing is trivial. Glyph ships a utility.

**Recommendation:** WS and SSE are MVP-tractable. Binary/protobuf schema recovery is a long tail — treat as a stage-4 extension. Document the gRPC h2c gap as a known limitation.

### 3j. Sensitive surfaces (RESEARCH.md §6j) — **holds; bot-mgmt landscape surveyed, FingerprintJS license flag**

RESEARCH.md names: bot-management challenge reversing (Akamai, Cloudflare, DataDome, PerimeterX/HUMAN, Kasada; browser-fingerprint surface); CAPTCHA-solving and challenge-evasion for access are part of the decoding surface. Hardware/firmware/RF RE excluded.

**Verified — bot-management landscape (factual survey, no bypass recipes):**

All five commercial vendors converge on roughly the same **five signal classes:** (1) TLS/HTTP fingerprint (JA3/JA4/HTTP2), (2) browser fingerprint (canvas/WebGL/audio/fonts/navigator), (3) behavioral (mouse, keyboard, timing), (4) IP/ASN reputation, (5) proof-of-work / interactive challenge. Differentiation is in weighting, ML model, and obfuscation/rotation strategy.

| Vendor | Challenge mechanism | Public RE | Anti-RE trend (2023+) |
|--------|---------------------|-----------|----------------------|
| **Cloudflare** | Turnstile (PoW + proof-of-space + web-API probing); Bot Management (Enterprise, JA4); "I'm Under Attack" 503→JS math→POST | GitLab Red Team tech note; Cloudflare JA4 blog (Aug 2024) | JA4 standardized enterprise-wide Aug 2024 |
| **Akamai** | Bot Manager (formerly Primary's Pixel/PSG sensor) — obfuscated JS sensor POSTs encrypted `sensor_data` → `/_abck` cookie | `Edioff/akamai-analysis`; `glizzykingdreko` Medium series; ScrapeBadger write-up (May 2026) | v3 sensor derives encryption keys from real-time JS-file hashes |
| **DataDome** | JS tag ("Device Check") + server SDKs → encrypted payload to `api-js.datadome.co` → `datadome` cookie | `xKiian/datadome-vm` (VM disassembler); `glizzykingdreko/datadome-encryption`; Scrapfly 2026 guide | **Build-time JS rebuilds** — every version functionally identical but structurally unique; recent versions move logic into a **custom bytecode VM** |
| **PerimeterX / HUMAN** | Bot Defender — behavioral + browser-fingerprint + network; `_px` cookies; interactive "press and hold" widget or CAPTCHA fallback; mobile SDKs | Biplov Dahal's iOS SDK RE; Scrapfly 2026 guide; several `github.com/topics/perimeterx` repos | Merger Jul 2022 (HUMAN + PerimeterX); F5 NGINX partnership embeds enforcement |
| **Kasada** | **Bytecode VM embedded in obfuscated JS** — PoW-style challenge → `x-kpsdk-ct` token + `kpsdk-ct` cookie | `umasii/ips-disassembler`; `0x6a69616e/kpsdk-solver` (Jun 2025); kernel.sh write-up | VM rotated + obfuscation keyed to runtime state; solver repos have short shelf life |

**The 2023+ anti-RE trend targets *durability* of public RE rather than one-off difficulty:** DataDome's structurally-unique build-time rebuilds, Kasada's embedded bytecode VM, Akamai v3's runtime-hash-derived keys, Arkose MatchKey's AI-resistant perturbations. All make signature-based tooling rot fast — which is exactly the problem Glyph's drift monitor (stage 10) is designed to solve. **Glyph's posture (per ADR-1):** decode-and-document — read the served challenge JS, derive the expected response format, emit a documented mechanism record into the catalog. Legal review on a per-target basis (RESEARCH.md §10) is mandatory before any of this surfaces in a non-research build.

**Verified — supporting surfaces:**
- **TLS fingerprinting:** JA3 (Salesforce, 2017) → JA4/JA4+ (FoxIO, 2023). JA4 unhashed (human-readable); JA4H (HTTP/2 SETTINGS + header order); JA4S (server); JA4X (X.509); JA4SSH. https://github.com/FoxIO-LLC/ja4
- **Client-impersonation stack:** `lwthiker/curl-impersonate` (Chrome/Edge/Safari/Firefox ClientHello + HTTP/2 framings); `bogdanfinn/tls-client` (Go-backed, Python bindings); `curl_cffi` (Python, drop-in `requests`-like API).
- **Browser fingerprinting:** **FingerprintJS is BSL-licensed** (Business Source License — source-available, free for dev/testing, **not for production/commercial use** without a commercial license). **Use CreepJS (MIT-style) or ThumbmarkJS for OSS embedding.** CreepJS documents ~30+ signals (canvas, WebGL, AudioContext, fonts, navigator, screen, timezone, hardwareConcurrency, deviceMemory, WebRTC IP leak). Academic lineage: Eckersley 2010 "Panopticlick" (EFF); Laperdrix et al. "Beauty and the Beast" survey.
- **CAPTCHA landscape:** hCaptcha (default on Cloudflare-proxied sites that opt out of Turnstile); reCAPTCHA v2 (checkbox/image-grid), v3 (invisible, 0.0–1.0 score), Enterprise; **Arkose Labs / FunCaptcha** (3D-rotation + "matchkey" puzzles, marketed as "AI-resistant," 225+ signals, 4th–6th-gen). Solving services: 2Captcha, Anti-Captcha (10+ year human-farm legacy), CapMonster Cloud, CapSolver (AI-first newer). **Solving services' own ToS typically forbid use that violates target-site terms** — Glyph does not integrate solvers per the user's "decode-and-document" framing.
- **Canonical academic reference:** Sivakorn et al. "I am Human: Human Verification API" (CCS 2016) — reCAPTCHA analysis.

**Legal posture (consistent across vendors):** analyzing the client-side challenge JavaScript *served to your own browser* is generally permissible; using the analysis to bypass protection on sites you do not own or are not authorized to test typically violates both the vendor's ToS and the protected site's terms, and may implicate CFAA (US) / Computer Misuse Act (UK) / similar in other jurisdictions. **Glyph's ADR-1 "decode-and-document" framing aligns with the former; per-target legal review (RESEARCH.md §10) is the gating control.**

**Recommendation:** §6j is in-scope as a decoding surface. Glyph documents mechanisms (challenge shape, signal taxonomy, expected response format) and emits them as catalog records — it does not ship solvers or bypass code. The drift monitor is the right tool to track when a vendor rotates their challenge (DataDome rebuilds, Kasada VM rotation). **License flag:** use CreepJS or ThumbmarkJS for browser-fingerprint analysis, not FingerprintJS (BSL).

---


## 4. The Rosetta centerpiece — prior art and novelty verdict (RESEARCH.md §5)

RESEARCH.md §5 is Glyph's thesis: *"the target's own UI is the Rosetta stone. When you load the real page, the API returns some record tagged with an opaque code, and the DOM renders a human label right next to it. If the capture stage records API payload + DOM at the same instant, a correlation pass matches API records to rendered labels (by shared ids, ordering, or numeric value) and auto-derives the dictionary: code → name, id → category, enum-int → meaning."*

**Prior-art research question:** is there published prior art for UI↔API correlation / DOM-payload alignment / automatic semantic dictionary derivation?

### 4.1 Verdict — Rosetta is novel, as a combination

Every individual half exists in mature form. **No published tool or paper derives code→meaning dictionaries by treating the rendered UI as semantic ground truth.**

| Half | Exists? | Source |
|------|---------|--------|
| Paired capture of API responses + DOM snapshots | **Yes** | Playwright Trace Viewer, WebdriverIO Trace Mode, CDP `DOMSnapshot`+`Network` |
| Schema inference from JSON samples | Yes | quicktype, genson |
| Traffic-based API discovery | Yes | Akto, Levo.ai, mitmproxy+HAR |
| UI-driven API spec inference | Yes (closest: structural only) | *Carving UI Tests*, ICSE 2023 |
| Probabilistic record-linkage confidence scoring | Yes | Fellegi-Sunter (1969); Splink |
| HITL low-confidence review UX | Yes | Label Studio, Prodigy |
| DOM `data-*` attribute mining | Conceptually | Heap analytics practice; no published tool |
| Browser-side taint tracking of API values | Yes (for security) | PanoptiChrome, Augur |
| **UI↔API correlation to derive code→meaning dictionaries** | **No published prior art found** | **Glyph's gap** |

### 4.2 The single closest published work

**"Carving UI Tests to Generate API Tests and API Specification"** (Yandrapally, Sinha, Tzoref-Brill, Mesbah; ICSE 2023, 41 citations) — https://arxiv.org/abs/2305.14692. Drives the web UI, captures XHR/fetch, infers REST endpoints + path parameters via "directed API probing," and emits an OpenAPI spec plus carved API-level tests. 98% precision / 56% recall on endpoint inference across 7 open-source apps. **Critical gap:** the output is *structural* (endpoints, params, response shapes) — it does **not** correlate opaque API code values (enum ints, status codes, type ids) with rendered DOM labels. DOM content is used only to identify navigation events and element interactions, not as semantic ground truth. **Glyph's Rosetta sits precisely in the gap** between what this paper captures and what a human analyst currently does by eyeballing the rendered page.

### 4.3 Other prior art surveyed

- **Academic API discovery/inference:** RESTler (MSR, ICSE 2019, ~397 cites — stateful REST fuzzer, requires pre-existing spec); RestTestGen (ICST 2020, ~256 cites); Schemathesis (OSS, property-based testing from OpenAPI); EvoMaster (2024 tool report); MINER (USENIX Sec 2023, 36 cites); **ARTE** (IEEE TSE 2023, 59 cites — pulls *realistic test data* from DBpedia, the closest "semantic" prior art in API-testing literature, but pulls meanings from external ontologies, not the target's own rendered UI).
- **Browser-side taint/data-flow:** PanoptiChrome; Augur (Northeastern PL); platform-independent JS taint (IEEE TS 2020); FP-tracer (PoPETS 2024); *Who Left Open the Cookie Jar?* (USENIX Sec 2018, 74 cites). **Verdict:** the technique ("follow an API field value as it propagates into the DOM") exists, but every published application targets *security* (XSS, secret leakage, cookie exfiltration), never *semantic dictionary derivation*.
- **Program synthesis from execution traces:** MIT MEng thesis (2016); Amazon/CMU POPL 2025; NeurIPS 2018 (71 cites). **Verdict:** "derive the function `code → label` from paired observations" *can* be framed as program synthesis from traces. No published work has done so for the UI↔API instance.
- **"Rosetta stone" analogy in RE/security literature:** used loosely — Ghidra's decompiler is called "your Rosetta Stone" for binary translation; Cornell Tech's "Rosetta" project (Jan 2026) studies database-input semantic-injection attacks on embedding models. **No published tool uses the analogy for UI↔API code-decoding.** Naming-wise, Glyph's "Rosetta" does not collide with a directly competing product in the same problem space.

### 4.4 Industry API security / discovery platforms — do they already do this?

- **Burp Suite** (PortSwigger) — "DOM Invader" finds DOM-XSS sources/sinks; "response extraction rules" define regex-extractable locations in responses; community "Burp DOM Scanner" ext auto-extracts regex matches from HTTP responses. **Gap:** treats DOM as attack surface, never as semantic ground truth; no API-code↔DOM-label pairing.
- **Postman** — generates collections *from specs*, not from traffic. Auto schema inference from samples is a 5+ year-old unaddressed community feature request.
- **Akto** (OSS, MIT) — traffic-based API discovery + inventory + DAST. ~40 built-in "data types" (Email, Phone, etc.) for *sensitive-data classification* by field-name/value regex. **Gap:** pattern-based field classification, not UI-derived semantic decoding.
- **Levo.ai** (commercial, eBPF) — auto-generates OpenAPI specs and annotates fields with sensitive-data types (PII/PSI/PHI) using "data type inferences." **Gap:** same as Akto — pattern-based, not UI-correlated. Verified by reading their blog directly.
- **Noname/Salt/Wallarm** — Salt's "business-logic learning" ML is opaque — **risk to monitor** (see §4.6).
- **SwaggerHub/Stoplight/Hoppscotch** — design-first editors, don't derive from traffic.

### 4.5 Capture-stage pairing — the missing half already exists

**Playwright Trace Viewer** (Microsoft, OSS, mature) — **the missing half Glyph stage 1 needs already exists.** Captures per-action DOM snapshots (Before/Action/After), network requests, console logs, screenshots, source location in a single correlated `trace.zip`. Verified by reading https://playwright.dev/docs/trace-viewer. **Gap:** gives you the API+DOM pairing for free, but does not itself correlate codes with labels — that is Rosetta's job. WebdriverIO DevTools service / Trace Mode is the analog. CDP `DOMSnapshot.captureSnapshot` + `Network.responseReceived` give programmatic access to the same data.

### 4.6 Confidence scoring and HITL review — reuse, don't reinvent

- **Fellegi-Sunter model** (1969; foundational) — probabilistic record linkage; produces match probability per record pair via per-field agreement/disagreement weights. **Directly applicable** to scoring "API record `status=3` ↔ DOM label 'Pending'": treat as a 1-field record-linkage problem. Implementation: **Splink** (UK MoJ Analytical Services, MIT-licensed, https://moj-analytical-services.github.io/splink). **Recommendation: adopt Splink** rather than inventing a bespoke scheme.
- **Schema matching surveys:** Rahm & Bernstein 2001 (208 cites); Shvaiko & Euzenat 2005 (1812 cites) — combinator/linguistic/constraint-based matching between schema elements. Useful for "which API field corresponds to which DOM element" (the alignment step before code↔label matching).
- **HITL labeling UX:** **Label Studio** (Heartex, Apache-2.0, mature — supports active learning, "select most informative samples for annotation," low-confidence queue + paginated review is canonical); **Prodigy** (spaCy team, commercial — scriptable, rapid binary accept/reject). **Recommendation: adopt Label Studio** (or a stripped-down fork) for the low-confidence review UI rather than building from scratch.

### 4.7 Recommended positioning pivot

Rather than "novel capture technique," position Rosetta as: *"semantic decoding layer over Playwright-Trace-Viewer-style paired captures, using Fellegi-Sunter-class confidence scoring and Label-Studio-class HITL review."* That framing makes the novelty crisp (the decoding layer + dictionary-emission + drift-monitoring) and the reuse explicit (don't reinvent capture, scoring, or labeling UI).

### 4.8 Risks to monitor (before claiming total novelty externally)

1. **Salt Security's "business-logic learning" ML is opaque.** If their internal ML actually does code→label mapping, it's an unpublished competitor — **demo before claiming total novelty** in any external write-up.
2. **The Carving-UI-Tests authors could extend their work** to semantic decoding in a follow-up paper — cite them defensively and differentiate explicitly on "we emit code→meaning dictionaries; they emit OpenAPI specs."
3. **Levo.ai's "data type inferences" wording is vague** — verified by blog read that they don't pair DOM labels with API codes, but worth a demo call before external claims.
4. **Cloudflare's ML API Discovery + Schema Learning** (Mar 2023, https://blog.cloudflare.com/ml-api-discovery-and-schema-learning) is the cleanest published production example of the discovery+schema half — cite defensively.

### 4.9 Open items / next actions

1. Read the full Carving-UI-Tests PDF directly (the page_reader returned only the chrome-extension PDF embedder stub) and verify whether their dynamic DOM analysis touches rendered text content at all.
2. Demo Akto, Levo, and Salt Security to confirm the gap.
3. **Prototype the Rosetta correlation pass over a real Playwright `trace.zip`** — this is the Phase-0 proof (RESEARCH.md §9, scoped concretely in §9 below).
4. Pick Splink vs. a small reimplementation for the confidence scorer.
5. Pick Label Studio vs. a stripped-down fork for the review UI.

---

## 5. Architecture validation — does the composable-stages design hold? (RESEARCH.md §4)

RESEARCH.md §4 proposes ten composable stages over a shared catalog (SQLite locally → service DB when shared): 1 Capture → 2 Catalog → 3 Schema-infer → 4 Rosetta decode → 5 Auth analyzer → 6 Gating profiler → 7 Backend fingerprint → 8 APK miner → 9 Codegen → 10 Drift monitor.

**Verdict: the decomposition holds.** Each stage maps to a real, maintainable tool (verified in §3 above), and the shared-catalog model is the right glue. Three architectural refinements this deep-dive surfaces:

### 5.1 The catalog store — promote to DuckDB before Postgres

RESEARCH.md §11 leaves the catalog store as an open question (SQLite local → shared DB later). This deep-dive recommends a **three-step promotion path** rather than a two-step:

1. **MVP: SQLite** (per RESEARCH.md §11) — embedded, single-file, zero-config, OLTP-optimized, public domain. Best for per-analyst MVP.
2. **Promotion step 1: DuckDB embedded** (MIT) — still single-file, no ops, but **vectorized OLAP execution** ideal for analytical queries over captured samples (group-by endpoint, aggregate enum values, drift diffs). https://duckdb.org/why_duckdb.html
3. **Promotion step 2: Postgres** — only when shared across multiple concurrent analysts/CI runs. Rich JSONB + GIN indexes ideal for raw payloads, but operational cost; overkill until multi-user.

**Prior art for an "API catalog store":** the concept exists at vendor level (IBM API Connect "Catalogs," Apideck unified API, Fern's "What is an API catalog" guide, digitalml) but those are commercial platforms, not a reusable schema. **Could not verify an open-source "API catalog store" schema Glyph could lift directly — building one is part of the work.**

### 5.2 The capture substrate — Playwright Trace Viewer is the pairing data

RESEARCH.md §4 stage 1 says: *"Records API payload and DOM at the same instant — that pairing is what makes stage 4 work."* This deep-dive confirms the pairing data already exists in **Playwright's `trace.zip`** (screenshots, DOM snapshots, network waterfall, source location, all correlated per-action). **Architectural implication:** stage 1 should drive Playwright with `--tracing on` and consume the `trace.zip` as the primary capture substrate, with mitmproxy as the wire-level sink for things Playwright can't capture (full WS frame bodies, non-browser traffic, HTTP/2 push). Don't reinvent the pairing — consume Playwright's.

### 5.3 The drift monitor — oasdiff as the engine, dictionary diff as the Glyph layer

RESEARCH.md §4 stage 10 says: *"re-capture on a schedule, diff schemas/dictionaries, alert on new codes, renamed fields, or changed gating."* This deep-dive confirms **oasdiff** (Apache-2.0, Go lib + CLI + GitHub Action, 506 distinct change types) as the schema-diff engine. **Architectural implication:** Glyph's drift monitor is a thin layer over oasdiff for schema drift, plus a custom **dictionary-diff** pass for Rosetta-emitted code→meaning dictionaries (oasdiff doesn't know about dictionaries — that's Glyph's value-add). The 2023+ anti-RE trend (DataDome rebuilds, Kasada VM rotation) makes drift monitoring on bot-management surfaces a concrete differentiator.

---

## 6. Competitive landscape — where Glyph fits

This section synthesizes the competitive-landscape research (Task 7, 23 tools surveyed) into a positioning statement.

### 6.1 The three closest competitors

1. **Akto** (OSS, MIT) — closest on the *capture→catalog→schema* half. 50+ traffic connectors, 1,000+ built-in tests, sensitive-data classification by field name/value regex. Auto-discovers APIs from traffic → emits OpenAPI. Aug 2024 added "discover APIs from GitHub" + AI-powered source-code discovery (Mar 2025). **Glyph differentiates** by adding Rosetta (DOM↔API code-decoding), auth analyzer with JS-bundle function location, gating profiler (IP-type/JA4/rate-limit), backend fingerprint library, APK/IPA miner, codegen to typed client, drift monitor with dictionary diff. Akto's "sensitive data" classification is regex-based field tagging; Glyph's Rosetta derives code→meaning dictionaries by treating the rendered UI as ground truth. https://github.com/akto-api-security/akto

2. **Levo.ai** (commercial, eBPF) — closest commercial analog of capture→OpenAPI, with sensitive-data annotation. Auto-discovers APIs and auto-generates OpenAPI specs, annotated with sensitive-data types (PII/PSI/PHI) using "data type inferences." **Glyph differentiates** by being *external-target* oriented (drives the target's UI), open-sourceable, and adding mobile RE + codegen + drift on dictionaries. Levo is server-side eBPF on your own traffic — it can't see a target you don't own. https://www.levo.ai

3. **MobSF** (OSS, **GPL-3.0**) — closest on the APK-miner half. 21.2k★, automated APK/IPA/APPX static + dynamic analysis, REST API (`/api/v1/scan`, `/api/v1/get_json`), extracts URLs, secrets, permissions, components. **Glyph differentiates** by emitting a structured endpoint catalog with samples + signing logic + deep-link map (MobSF stops at security findings), by feeding the catalog forward into schema inference / Rosetta / codegen, and by combining mobile findings with live traffic. **The GPL-3.0 license blocks embedding MobSF as a library — Glyph drives it as a subprocess or reimplements the extraction.** https://github.com/MobSF/Mobile-Security-Framework-MobSF

### 6.2 Has anyone built capture + schema inference + codegen end-to-end?

**Partial yes, full no.** The closest published examples:
- **Akto** does capture→catalog→OpenAPI, then stops. No codegen, no Rosetta.
- **Levo.ai** does eBPF-capture→catalog→OpenAPI+sensitive-data-tagging, then stops. No codegen, no Rosetta, no mobile.
- **Cloudflare API Gateway** does edge-capture→ML-discovery→schema-learning (Mar 2023), then stops. No codegen, no Rosetta, no mobile, no external-target orientation. https://blog.cloudflare.com/ml-api-discovery-and-schema-learning
- **site2cli** (lonexreb/site2cli, small GitHub project) — "Discovery Pipeline captures browser traffic and converts it into structured interfaces: Traffic analysis, path normalization, schema inference." A hobby-scale analog of Glyph's MVP. Worth watching but not production.
- **Postman** does collection→OpenAPI (manually curated, not traffic-discovered) and pairs with openapi-generator for codegen — but the discovery step is manual.

**No published tool combines traffic capture + schema inference + codegen + Rosetta-style semantic decoding + mobile RE + drift.** Glyph's full pipeline is genuinely novel as a *combination* (matches §4's verdict on the Rosetta half specifically).

### 6.3 Has anyone built API discovery + APK/native RE together?

**No.** MobSF is the only OSS tool that does both APK static analysis *and* URL/secret extraction, but it does not catalog APIs as endpoint records with samples and does not pair the static findings with live traffic. Commercial mobile-appsec tools (NowSecure, Appknox, Ostorlab, Corellium, Data Theorem) focus on vulnerability scoring, not catalog/codegen. **Greenfield for Glyph** — confirms Task 5's conclusion.

### 6.4 Honest differentiation

Glyph is **not**:
- "a better Burp" — Burp wins on interactive pentesting (GUI, BApp Store, Repeater).
- "a better Postman" — Postman wins on collaboration.
- "a better Akto" — Akto wins on enterprise API inventory for your own traffic.

Glyph **is** the only proposed tool that combines **(a) external-target traffic capture with DOM pairing, (b) Rosetta semantic decoding, (c) APK/IPA mining for endpoint catalogs + signing logic, (d) codegen, and (e) drift monitoring on dictionaries** into one pipeline aimed at *reverse-engineering unfamiliar targets*.

**Honest caveats:**
- Salt Security's opaque "business-logic learning" ML *might* do something Rosetta-like internally — demo before claiming total novelty (§4.8 risk 1).
- Cloudflare's ML API Discovery + Schema Learning is a published production example of the discovery+schema half — cite defensively.
- The Rosetta novelty is a *combination* novelty, not a *technique* novelty — every half exists. Position accordingly (§4.7).

### 6.5 License/maintenance summary (verified)

| Tool | License | Last verified release | Active? |
|---|---|---|---|
| Burp Suite | Proprietary | 2025.3 (Apr 2025) | Yes |
| OWASP ZAP | Apache-2.0 | 2.16.1 (2025) | Yes |
| Postman | Closed | continuous SaaS | Yes |
| Akto | MIT | continuous (Mar 2026 docs) | Yes |
| Levo.ai | Commercial | Jan 2026 platform update | Yes |
| Cloudflare API Gateway | Commercial | active since Mar 2023 | Yes |
| openapi-generator | Apache-2.0 | v7.24.0 (Sep 28 2025) | Yes |
| quicktype | Apache-2.0/MIT | active | Yes |
| oasdiff | Apache-2.0 | active | Yes |
| Optic | (was MIT) | **Archived Jan 12 2026** | **Dead** |
| mitmproxy | MIT | v12.2.3 (May 2025) | Yes |
| HTTP Toolkit | Apache-2.0/MIT | active | Yes |
| MobSF | **GPL-3.0** | v4.5.1 (Aug 2025) | Yes |

---


## 7. Open questions resolved (RESEARCH.md §11)

RESEARCH.md §11 lists five open questions. This deep-dive resolves four and leaves one for the user.

### 7.1 Repo/service split — **resolved: monorepo with stages as packages**

RESEARCH.md asks: *"one repo with stages as packages, or capture-tool + catalog-service?"*

**Resolution: monorepo with stages as Python packages, sharing a catalog library.** Rationale:
- Every stage reads/writes the same catalog — a service boundary between capture and catalog adds network + serialization overhead with no benefit at MVP scale.
- The catalog *is* the integration point; making it a library (not a service) keeps the MVP single-process and debuggable.
- A service split becomes worthwhile only when (a) the drift monitor needs to run on a schedule independent of capture, or (b) multiple analysts share a catalog. Both are post-MVP.
- **Concrete structure (recommended):**
  ```
  glyph/
  ├── glyph/                  # the package
  │   ├── catalog/            # the shared store (SQLite/DuckDB abstraction)
  │   ├── capture/            # stage 1 — mitmproxy addon + Playwright driver
  │   ├── schema/             # stage 3 — genson wrapper + enum detection
  │   ├── rosetta/            # stage 4 — UI↔API correlation (the centerpiece)
  │   ├── auth/               # stage 5 — signing analyzer
  │   ├── gating/             # stage 6 — JA4/IP/rate-limit profiler
  │   ├── fingerprint/        # stage 7 — backend family signatures
  │   ├── mobile/             # stage 8 — APK/IPA miner
  │   ├── codegen/            # stage 9 — openapi-generator + quicktype wrappers
  │   ├── drift/              # stage 10 — oasdiff + dictionary diff
  │   └── cli.py              # the `glyph` entrypoint
  ├── tests/
  ├── pyproject.toml
  └── README.md
  ```
- This matches how Akto and mitmproxy itself are structured (single package, multiple modules).

### 7.2 Catalog store — **resolved: SQLite → DuckDB → Postgres (three-step)**

RESEARCH.md asks: *"start SQLite (local, per-analyst), promote to a shared DB later?"*

**Resolution: yes, but insert DuckDB as the middle step.** See §5.1 for the full rationale. Short version: SQLite for MVP, DuckDB embedded when drift analytics start mattering (still single-file, no ops), Postgres only when shared across users. DuckDB's vectorized OLAP is ideal for the analytical queries drift monitoring needs (group-by endpoint, aggregate enum values, diff dictionaries) — and it's still a single embedded file with no operational cost.

### 7.3 Mobile-MITM/APK in CI vs physical device — **resolved: Android headless, iOS needs device**

RESEARCH.md asks: *"How much of the mobile-MITM/APK flow can run headless in CI vs. needs a physical device?"*

**Resolution:**
- **Android static analysis (APK miner, stage 8): fully headless/CI-friendly.** apktool + jadx + apk-mitm + Frida (subprocess) all run in CI with no device. The APK is the input; the catalog entries + signing-logic extraction are the output.
- **Android dynamic analysis (MITM capture, runtime hooking): emulator-tractable for most cases.** Android Emulator (AVD) + Frida + apk-mitm-patched APK + mitmproxy covers the common case. Hardware needed only for apps that detect emulators (banking, some anti-cheat).
- **iOS static analysis: headless after decryption.** iCDump/class-dump + Mach-O parsing (LIEF) run in CI, but the IPA must be decrypted first — and decryption requires a jailbroken device. **No pure-host path exists for iOS.**
- **iOS dynamic analysis: physical jailbroken device required.** No emulator substitute. Out of scope for MVP CI.
- **Architectural implication:** ship Android support first (CI-tractable end-to-end). Document iOS as "requires jailbroken device — analyst workflow, not CI." This matches how MobSF structures its iOS support.

### 7.4 Handoff line to InjectX — **deferred to the user**

RESEARCH.md asks: *"Where exactly is the handoff line to InjecX when an endpoint needs a tunnel to reach?"* (Note: ADR-1 spells it "InjectX"; RESEARCH.md §11 spells it "InjecX" — a typo to fix.)

**Resolution: deferred.** This is a product-boundary decision between two projects (Glyph and InjectX) that only the user can make. The factual input this deep-dive provides: Glyph's job is to *discover and decode* a target's surface; InjectX's job is to *route traffic* to reach endpoints that aren't directly accessible. The natural handoff is at the catalog — Glyph emits an endpoint record (URL, auth, gating profile), and if that endpoint is unreachable from the analyst's network, the record carries enough metadata (host, port, required egress) for InjectX to decide whether and how to tunnel. **Concrete recommendation:** define the handoff as a catalog-entry schema field (`reachability: direct | needs_tunnel | unreachable`) plus an optional `tunnel_hint` (e.g., "residential IP required," "JA4 must match Chrome"). The user should validate this against InjectX's actual interface once InjectX has one.

### 7.5 Naming — **deferred to the user**

RESEARCH.md asks: *"Naming."* Per `user/preferences.md` (Session 1 correction, 2026-07-29): *"Naming and scope are the user's call — judge a name on its own merit; do NOT couple a standalone tool to sibling projects."* This deep-dive does not propose a rename. The "Glyph" name is clear (per RESEARCH.md: *"the tool decodes a target's opaque symbols (codes, ids, enums) into meaning, the way a glyph is a mark that carries meaning once you can read it"*), does not collide with a directly competing product (§4.3), and is short + memorable. **Recommendation: keep "Glyph" unless the user has a reason to change.**

---

## 8. Phase-0 proof — concrete scoping (RESEARCH.md §9)

RESEARCH.md §9 says: *"Pick any target with obvious opaque codes and a visible UI. Run stages 1–4: 1. Drive the UI + capture (API + DOM). 2. Rosetta → auto-derive its code dictionary. 3. Verify the derived mappings against what a human would read off the UI. Success = the tool reproduces by machine what an analyst would do by hand, faster and re-runnably."*

This deep-dive scopes that concretely.

### 8.1 Target selection criteria

The Phase-0 target should have:
- **Obvious opaque codes** — numeric type ids, integer enums, or status codes in API responses that a human currently decodes by looking at the rendered UI.
- **A visible, driveable UI** — a web app where the same codes appear as human-readable labels in the DOM (not a pure API-only service).
- **Stable enough to re-run** — the target shouldn't change its API shape during the proof (a few days).
- **Authorized to analyze** — per ADR-1 and RESEARCH.md §10, the target must be one the user is authorized to analyze. A self-hosted demo app, an open-source app with a public deployment, or the user's own product are all valid. **Do not pick a third-party production site without explicit authorization.**

**Concrete candidate targets (the user picks):**
- **A public open-source app with a demo deployment** — e.g., a self-hosted Ghost/Mastodon/WordPress instance, or a demo deployment of an open-source admin panel (the user controls the instance, so authorization is clear).
- **The user's own product** (if any) — highest authorization, real codes.
- **A demo app built for the proof** — fastest to set up: a small Next.js/Flask app with a few endpoints that return integer status codes the UI renders as labels. Full control, no external dependencies, but the "codes" are contrived (less impressive proof).

**Recommendation:** a self-hosted open-source app with a public demo (e.g., a Mastodon instance the user spins up) — real codes, real UI, full authorization, re-runnable.

### 8.2 Done criteria

The Phase-0 proof is **done** when:
1. `glyph capture <target>` drives the UI (Playwright + `--tracing on`) and captures API + DOM pairs into the catalog (SQLite).
2. `glyph schema` infers JSON Schemas per endpoint (genson) and flags enum candidates (low-cardinality fields).
3. `glyph rosetta` correlates API code values with rendered DOM labels and emits a code→meaning dictionary with confidence scores (Splink-style).
4. Low-confidence rows are queued for human review (Label Studio or a stripped-down fork).
5. **Verification:** a human reads the derived dictionary against what they would read off the UI by hand, and the high-confidence rows match. The success bar is **>80% precision on high-confidence rows** (confidence ≥ 0.9) — not 100% recall, since low-confidence rows go to the human queue by design.

### 8.3 Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The target's UI doesn't render labels next to the codes (e.g., codes drive styling, not text) | Medium | High — Rosetta can't correlate | Pick a target where labels are visible (status badges, type names in lists). Verify by hand before committing. |
| The API and DOM don't share a stable id (positional correlation only) | Medium | Medium — lower confidence | Splink handles positional + value-inferred matching; flag low-confidence rows for human review. |
| The target requires auth to reach the coded endpoints | High (most apps do) | Low — Playwright can log in | Document the auth flow as part of capture; Glyph's auth analyzer (stage 5) is a Phase-0 stretch goal, not a blocker. |
| The target rate-limits or bot-detects the driver | Low (self-hosted) | Low | Use a self-hosted target for the proof; gating profiler (stage 6) is post-Phase-0. |
| Playwright's `trace.zip` doesn't capture the specific DOM state where the label appears | Low | Medium — missed pairing | Drive the UI with explicit waits (`page.wait_for_selector`) so the DOM is settled when the trace snapshot fires. |
| The dictionary-emission format is wrong (too rigid, too loose) | Medium | Medium — rework | Start with a simple `{code, label, confidence, evidence}` schema; iterate based on what the human review surfaces. |

### 8.4 What the Phase-0 proof does NOT include (scope discipline)

- **No mobile RE** (stage 8) — Android APK miner is post-Phase-0.
- **No bot-management decoding** (§6j) — the target is self-hosted, so no anti-bot.
- **No codegen** (stage 9) — codegen off a single target over-fits (RESEARCH.md §8).
- **No drift monitor** (stage 10) — needs two captures over time; Phase-0 is one capture.
- **No gating profiler** (stage 6) or **backend fingerprint** (stage 7) — self-hosted target doesn't need them.

The Phase-0 proof is **stages 1–4 only** — the minimum to validate that Rosetta works. If it reproduces hand-analysis faster and re-runnably, greenlight the rest (per RESEARCH.md §8).

### 8.5 Estimated effort

Rough, for a single engineer building it fresh:
- Stage 1 (Capture): 2–3 days — mitmproxy addon + Playwright driver + trace.zip consumption.
- Stage 2 (Catalog): 1–2 days — SQLite schema + flow normalization + dedup.
- Stage 3 (Schema-infer): 1 day — genson wrapper + enum-candidate detection.
- Stage 4 (Rosetta): 5–8 days — the hard part. DOM parsing, correlation strategies (exact-id, positional, value-inferred), Splink integration, confidence scoring, dictionary emission.
- HITL review UI: 2–3 days — Label Studio integration or a minimal fork.
- **Total: ~2–3 weeks for a working Phase-0 proof.** This is the gate for building the rest.

---

## 9. Recommendations — what to do next

Ordered by priority:

1. **Greenlight the Phase-0 proof (§8).** Pick a target, build stages 1–4 minimally, verify Rosetta auto-derives the code dictionary. This is the gate for everything else. **~2–3 weeks.**
2. **Adopt the architecture in §7.1** (monorepo, stages as packages, catalog as a library). Don't service-split at MVP.
3. **Adopt the catalog-store promotion path in §5.1/§7.2** (SQLite → DuckDB → Postgres).
4. **Adopt Playwright `trace.zip` as the stage-1 capture substrate** (§5.2) — don't reinvent the API+DOM pairing.
5. **Adopt Splink for confidence scoring and Label Studio for HITL review** (§4.6) — don't reinvent either.
6. **Ship the Daraja callback verification recipe** (§3g) as an early concrete deliverable — it's a known Kenya-priority integration hazard and a clean differentiator.
7. **Update RESEARCH.md §6b** to say "JA4/JA4+ (JA3 retained for backward compat)" instead of "JA3/JA4" — JA4 is the current standard (Cloudflare enterprise-wide Aug 2024).
8. **Fix the InjectX/InjecX typo** in RESEARCH.md §11 (ADR-1 spells it "InjectX").
9. **Demo Akto, Levo, and Salt Security** before any external novelty claim about Rosetta (§4.8) — confirm the gap.
10. **Cite Cloudflare's ML API Discovery + Schema Learning defensively** in any external write-up — it's the cleanest published production example of the discovery+schema half.
11. **Defer the InjectX handoff line and naming to the user** (§7.4, §7.5).

---

## 10. Honest caveats (RESEARCH.md §10, reaffirmed)

RESEARCH.md §10's caveats all hold; this deep-dive adds nuance:

- **Semantics still need a human confirm** on ambiguous cases — the tool narrows, it doesn't remove judgment. Splink's confidence scoring + Label Studio's HITL review are the mechanism.
- **Anti-bot is an arms race** — the 2023+ trend (DataDome rebuilds, Kasada VM rotation, Akamai v3 runtime-hash keys, Arkose MatchKey) targets *durability* of public RE. Glyph's drift monitor is the right tool to track rotations, but it doesn't make the arms race go away. **Per-target legal review (RESEARCH.md §10) is mandatory before any bot-management decoding surfaces in a non-research build.**
- **The tool itself needs maintenance** — capture drivers and fingerprints rot as targets evolve. This is exactly what the drift monitor (stage 10) is for, but it applies to Glyph's own fingerprints too.
- **Legal/ToS vary by target and jurisdiction** — a per-target check belongs in the workflow. The bot-management legal posture (§3j) is consistent: analyzing JS served to your own browser is generally permissible; bypassing protection on third-party sites is not. Glyph's ADR-1 "decode-and-document" framing aligns with the former.
- **Responsible use** — Glyph defeats anti-bot, CAPTCHA, and access-control systems as part of its decoding surface. Use it against targets you're authorized to analyze. Credential and card values are never stored or logged. This is a tool for understanding and integrating, not for abuse — but understanding a surface necessarily means you can circumvent it.
- **WASM RE is immature** (§3b) — Glyph can document WASM-based logic hiding but cannot fully decode obfuscated WASM control-flow flattening with current tools. Flag as an open research problem.

---

## 11. References

### Glyph's own docs
- `RESEARCH.md` — the canon (scope, technique catalog, architecture, phasing).
- `.context/memory/plans/decisions.md` — ADR-1 (standalone, domain-neutral; defeats as a natural consequence of decoding).
- `.context/memory/reviews/2026-07-30-rosetta-prior-art.md` — full Rosetta prior-art research (Task 4).

### Supporting research notes (archived)
- `/home/z/my-project/tool-results/task3/capture_schema_codegen_research.md` — capture + schema inference + codegen tools (mitmproxy, Playwright, HAR, genson, quicktype, openapi-generator, oasdiff, DuckDB).
- `/home/z/my-project/tool-results/task5/js_native_mobile_re_research.md` — JS deobf + native/in-memory RE + mobile RE (Frida, Ghidra, angr, jadx, apktool, apk-mitm, MobSF, iCDump, etc.).
- `/home/z/my-project/tool-results/task6a/bot-management-research.md` — bot-management landscape (Cloudflare, Akamai, DataDome, HUMAN, Kasada, JA4, FingerprintJS, CAPTCHA).
- `/home/z/my-project/tool-results/task6b/payments-research.md` — payment integration surfaces (Stripe, PayPal, Adyen, Checkout.com, M-Pesa Daraja, Airtel, T-Kash, Google Play Billing, Apple StoreKit 2).
- `/home/z/my-project/tool-results/task7/competitive-landscape-research.md` — competitive landscape (23 tools: Burp, ZAP, Postman, Akto, Levo, MobSF, etc.).

### Key external sources (verified online, 2025–2026)
- **mitmproxy** v12.2.3 (May 2025), MIT — https://docs.mitmproxy.org/stable/api/events.html
- **Playwright** Trace Viewer + `routeWebSocket` (v1.48+, Oct 2024), Apache-2.0 — https://playwright.dev/docs/trace-viewer
- **genson** v1.4.0, MIT — https://github.com/wolverdude/genson
- **quicktype** v23.2.0, Apache-2.0 — https://github.com/glideapps/quicktype
- **openapi-generator** v7.24.0 (Sep 28 2025), Apache-2.0 — https://github.com/OpenAPITools/openapi-generator
- **oasdiff**, Apache-2.0 — https://www.oasdiff.com
- **DuckDB**, MIT — https://duckdb.org/why_duckdb.html
- **Frida** v17.16.4 (Jul 21 2025), GPLv2+commercial — https://frida.re
- **Ghidra** 11.4.3 (Dec 2025), Apache-2.0 — https://github.com/NationalSecurityAgency/ghidra
- **angr**, BSD-style — https://github.com/angr/angr
- **jadx**, Apache-2.0 — https://github.com/skylot/jadx
- **apktool** v2.9.3, Apache-2.0 — https://github.com/iBotPeaches/Apktool
- **apk-mitm**, MIT — https://github.com/niklashigi/apk-mitm
- **MobSF** v4.5.1 (Aug 2025), GPL-3.0 — https://github.com/MobSF/Mobile-Security-Framework-MobSF
- **webcrack** v2.16.0 (~Apr 2025), MIT — https://github.com/j4k0xb/webcrack
- **JA4/JA4+** (FoxIO, 2023) — https://github.com/FoxIO-LLC/ja4
- **curl-impersonate** — https://github.com/lwthiker/curl-impersonate
- **Splink** (Fellegi-Sunter implementation), MIT — https://moj-analytical-services.github.io/splink
- **Label Studio**, Apache-2.0 — https://labelstud.io
- **Akto**, MIT — https://github.com/akto-api-security/akto
- **Levo.ai** — https://www.levo.ai
- **Cloudflare ML API Discovery + Schema Learning** (Mar 2023) — https://blog.cloudflare.com/ml-api-discovery-and-schema-learning
- **Carving UI Tests** (Yandrapally et al., ICSE 2023) — https://arxiv.org/abs/2305.14692
- **M-Pesa Daraja** — https://developer.safaricom.co.ke
- **Stripe** webhooks — https://docs.stripe.com/webhooks
- **Apple StoreKit 2** — https://developer.apple.com/documentation/storekit

### Could-not-verify-online items (honest gaps)
- Airtel Money callback signature scheme (§3g).
- T-Kash official API surface (§3g) — no public developer portal found.
- Checkout.com exact signature header name and idempotency-key TTL (§3g).
- Adyen idempotency-key TTL (§3g).
- Specific Kasada customer ToS wording (§3j).
- Whether HUMAN's Bot Defender sensor still emits the legacy `_px` cookie namespace after the merger (§3j).
- Salt Security's internal "business-logic learning" ML behavior (§4.8) — opaque, demo required.
- Whether the Carving-UI-Tests authors' dynamic DOM analysis touches rendered text content (§4.9) — PDF fetch returned only the chrome-extension stub.

---

*End of deep-dive. For the canon, see [RESEARCH.md](RESEARCH.md). For the protocol that produced this document, see `.context/kickoff.md`.*
