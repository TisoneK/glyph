# Office 001 — accomplishments record (permanent)

- Opened: 2026-07-29
- Closed: 2026-09-22
- Sessions: 32

The frozen office lives at history/office-001/ until it is zipped into
archive/office-001.tar.gz. This record stays in history/ forever — even after
the tarball is garbage-collected, the office is never forgotten. Not read at
session start; deliberate lookback only.

## Accomplished

This office took Glyph from a research canon to a working, installable,
tested package — and lived through three protocol core jumps.

- **Foundation:** research phase (RESEARCH.md, RESEARCH-DEEP-DIVE.md) →
  architecture → one subpackage per pipeline stage over a shared catalog.
- **Catalog:** SQLite store, multi-target schema (`targets` table plus a
  `target_id` on every data row), persisted/restored active target, every
  display command filtered to the current target.
- **Capture:** HAR import; live Playwright capture in auto and browse
  modes; CDP-attach to the user's real browser as the primary path with a
  launch fallback; continuous real-browser sessions with TUI-controlled
  stop/detach; mitmproxy addon; geo-block detection and recovery.
- **Analysis stages:** schema inference, rosetta field naming, sensitive
  detection with masking, bounded SNI bug-host hunting, VPN-config
  decoding, mobile static mining (APK/IPA and the split-APK family),
  OpenAPI codegen, drift, fingerprint, gating, auth, review queue.
- **Parallel analysis pipeline:** schema→rosetta chained while sensitive
  and snihunt run beside it; profiled at ~1.4x on network-bound runs and
  ~1.0x CPU-bound (GIL), with no regression.
- **TUI (Textual):** home screen with analysis-stage selection, live
  capture streaming, flows / DOM / dictionary / schema / endpoint-data
  views, VPN-decoder form, target picker, quit confirmation with a
  graceful tracked-worker shutdown.
- **Verification:** live capture against example.com and linebet.com; the
  live TUI streamed a real capture end to end in a pty; the suite grew to
  195 passed / 5 skipped; ruff wired into the pre-commit and exit gates.
- **Protocol:** core 0.3.0 → 0.5.0 → 0.8.0 → 2.0.3 (office architecture),
  including the Windows line-ending corruption diagnosis, the live-office
  grouping, and the `.context/` → `.context_ledger/` rename.

## Decisions still in force

- **ADR-1/ADR-3** — Glyph is a standalone, general-purpose
  reverse-engineering toolkit; no coupling to sibling projects.
- **ADR-2** — monorepo: stages as subpackages over a shared catalog.
- **ADR-6** — capture is HTTP/application-layer; raw packet capture is out
  of core.
- **ADR-8** — `rich` is the CLI layer and the base package's one runtime
  dependency.
- **ADR-9** — the TUI is presentation over `glyph.db`; the engine stays
  headless.
- **ADR-10** — SNI hunting is bounded active recon, run after sensitive.
- **ADR-11** — VPN-config decoding is file-triggered and lives behind the
  `[crypto]` extra.
- **ADR-12** — multi-target catalog invariants: `set_target()` activates,
  `clear_target()` wipes only that target, every write carries a NON-NULL
  `target_id`, reads filter to the active target, and `capture` accumulates
  where `run` clears.
- **ADR-14** — CDP-attach to the user's browser is primary; a
  Playwright-launched browser is the fallback.
- **ADR-15** — analysis stages run concurrently; schema→rosetta stays a
  chain because rosetta reads schema output.
- **ADR-16** — the active target is persisted and restored for every
  display command.
- **ADRs 17–23** — TUI stage selection and App-level CSS; quit lifecycle,
  detached SNI and target switching; endpoint-data view; real-browser
  capture with TUI detach; cross-platform quit confirmation; pumped capture
  lifecycle; geo-block recovery and explicit browser targeting.

## Open threads

Actionable items re-seeded into the new office's backlog:

- Windows on-device verification of the live browser path (CDP attach,
  streaming TUI, stop/detach, clean shutdown).
- Report and fix two core 2.0.3 `.ps1` port defects upstream, plus the
  `parse_ports` engine preference that makes `ledger-sync verify` return 3
  on Windows.
- Real-world browse-mode verification on the user's primary browser against
  an auth-protected target.
- A bounded graceful-shutdown timeout for pathological browser/network
  hangs.
- Strict historical capture-session isolation for all-tabs mode.

Parked knowledge (findings, questions, deferred work):

- **Finding:** on Windows a checkout can leave CRLF copies of core files
  while `git status` still reports the tree clean (stale stat cache), so
  `verify` fails on every file and `git checkout --` silently does nothing;
  deleting the files and re-checking them out restores LF, and the
  recursive `.gitattributes` that ships with 2.x prevents recurrence.
- **Finding:** `git add --renormalize .` must not be run repo-wide on this
  machine — with the root `.gitattributes` lacking `text=auto`, it would
  stage CRLF into product-file blobs. Normalize per path instead.
- **Open question:** retarget the base package from 3.9-compatible stdlib
  dataclasses to Python 3.13 + Pydantic (user preference; decision
  pending).
- **Deferred:** DuckDB catalog backend; `glyph capture proxy` (mitmproxy)
  for Firefox/Safari users, parked until someone asks for it.
