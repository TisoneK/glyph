# Research note — capture-layer scope + mobile package scope (Session 13)

- **Date:** 2026-07-31
- **Agent:** Claude Code / claude-opus-4-8
- **Purpose:** Online research to ground two scope ADRs the user flagged as missing —
  (A) raw-packet `.cap`/pcap decoding vs HTTP/HAR-level capture, and (B) mobile package
  handling beyond a single APK (XAPK / APKS / APKM / split APKs / OBB). Feeds **ADR-6** and
  **ADR-7** in `plans/decisions.md`.

## A. Capture layer — pcap/.cap vs HTTP

- **`.cap` / `.pcap` / `.pcapng` are packet-level** (libpcap; pcapng is the newer container).
  They hold raw frames, not HTTP semantics.
- **mitmproxy has no native pcap I/O** — it is an HTTP-layer intercepting proxy ("tcpdump for
  HTTP"), covering HTTP/1, HTTP/2, HTTP/3, and WebSockets. To go from pcap → HTTP you need
  three extra steps: TCP stream reassembly, TLS decryption (via an `SSLKEYLOGFILE` or a
  decrypting proxy like PolarProxy that writes a decrypted pcap), and HTTP parsing.
- **Extracting HTTP from pcap in Python is fiddly.** `pyshark` spawns `tshark`; even *with* a
  keylog file, users report it often does not expose decrypted application-data cleanly (only
  Wireshark's UI reliably shows it). Without the TLS keys you cannot recover URLs from HTTPS at
  all. So a pcap → HTTP importer is real work and lower-fidelity than proxy/browser capture.
- **When packet-level genuinely matters:** non-HTTP protocols (custom TCP/UDP binary, MQTT,
  raw protobuf over h2c), QUIC/HTTP-3 when you cannot MITM the proxy (decryptable in Wireshark
  with a keylog), or passive-tap-only situations. These are a **different tool class**
  (Wireshark + `pbtk`/`protoc --decode_raw` + Frida), not Glyph's HTTP-semantic surface.
- **Mobile angle:** on-device packet capture (e.g. PCAPdroid) can produce pcap with TLS
  decryption via a local VPN + mitm, but the output still needs the same pcap → HTTP step.

## B. Mobile packages — APK / AAB / splits / XAPK / APKS / APKM / OBB

- **APK** = a single Android package (a zip: `classes*.dex`, `lib/`, `res/`, manifest).
- **AAB (Android App Bundle)** = Google Play's *publishing* format; not directly installable —
  `bundletool` splits it into APKs server-side. You download APKs from stores, not AABs.
- **Split APKs** = how modern apps actually ship: `base.apk` + `config.<abi>.apk` (native
  libs per architecture), `config.<density>.apk` (resources), `config.<lang>.apk` (strings).
- **XAPK** = a third-party **zip** bundling `base.apk` + the split config APKs + an optional
  `Android/obb/` dir + `manifest.json`. Not an Android standard; used by APKPure etc.
- **APKS** = `bundletool`'s "APK Set" archive (a zip; `splits/` with `base-master.apk` + splits,
  or a universal APK). **APKM** = APKMirror's proprietary bundle (same idea).
- **OBB** = expansion files (assets/data), pushed to `/sdcard/Android/obb/<pkg>/`.
- **Static-mining implication:** endpoint/URL strings live across **base.apk dex + resources**,
  **split config `.so` native libs**, and **OBB assets** — so mining only a single top-level
  APK misses endpoints. To be thorough, treat any of these as "a zip that may contain one or
  more APKs plus OBB/asset blobs" and recurse one level, scanning every inner APK + OBB.

## Sources

- mitmproxy is an HTTP-layer proxy (no native pcap); SSLKEYLOGFILE + Wireshark for TLS —
  https://www.koyeb.com/blog/inspect-tls-encrypted-traffic-using-mitmproxy-and-wireshark ,
  https://github.com/mitmproxy/mitmproxy/issues/2938
- PolarProxy decrypts TLS and writes a decrypted pcap; PCAPdroid on-device capture —
  https://emanuele-f.github.io/PCAPdroid/tls_decryption.html
- pyshark/tshark TLS-decryption limitations —
  https://github.com/KimiNewt/pyshark/issues/463 , https://github.com/KimiNewt/pyshark/issues/417
- gRPC/protobuf + QUIC/HTTP-3 packet-level RE —
  https://labs.ioactive.com/2021/07/breaking-protocol-buffers-reverse.html ,
  https://blog.elmo.sg/posts/parsing-decrypted-quic-traffic-in-wireshark/
- XAPK structure (base + split configs + OBB + manifest.json); OWASP MASTG XAPK technique —
  https://mas.owasp.org/MASTG/techniques/android/MASTG-TECH-0145/ ,
  https://techyorker.com/3-ways-to-install-split-apks-xapk-apkm-on-any-android-device/
- bundletool / AAB → APK Set (.apks) / universal APK —
  https://developer.android.com/tools/bundletool
