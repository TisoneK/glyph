# Agent Sessions (append-only)

One entry per agent session, newest at the bottom. Never edit or delete
past entries — append corrections instead.

<!-- TEMPLATE — copy below the last entry:
---
## YYYY-MM-DD — Session N
- **Agent:** <name> | **Model:** <model id> | **Platform:** <machine/sandbox + OS> | **Role:** <engineer, or overlay from .context/core/roles/> | **Core:** <version from .context/core/VERSION>
- **Task:** <what this session set out to do>
- **Commits:** <count> (<first-sha>..<last-sha>)
- **Outcome:** <done / partial / blocked — one line>
- **Open items:** <pointers into tasks/backlog.md, or "none">
- **Report:** .context/memory/reviews/YYYY-MM-DD-review.md
-->

---
## 2026-07-29 — Session 1
- **Agent:** Claude Code | **Model:** claude-opus-4-8 | **Platform:** bao@local macOS (Darwin 24.6.0) | **Role:** engineer | **Core:** 0.3.0
- **Task:** Bootstrap the Glyph repo — initialize `.context/`, land the reverse-engineering research doc, push to GitHub.
- **Commits:** 2 — `55df6da` (docs: RESEARCH.md + README + .gitignore) + this `chore(context):` bootstrap commit.
- **Outcome:** done — repo created at `~/Code/glyph`, moved from `~/Desktop`, `.context/` bootstrapped (core 0.3.0) and registered in the package fleet.md, memory filled, pushed to `origin/main`.
- **Open items:** see `tasks/backlog.md` — MVP stages 1–4 + drift, Phase-0 proof.
- **Report:** none (bootstrap session).

---
## 2026-07-30 — Session 2
- **Agent:** Super Z | **Model:** unknown (system prompt does not state the exact GLM version; recorded `unknown` per Pitfall #25) | **Platform:** Z.ai cloud sandbox (Linux, workspace `/home/z/my-project/glyph`) | **Role:** engineer | **Core:** 0.3.0
- **Task:** Thorough read-through of the `.context/` protocol end-to-end (core 0.3.0) — understand the bootstrap → entry → execution → memory-update → sync/harvest loop, with deep focus on the `core/` and `memory/` modules; refresh the root `AGENTS.md` with a compact Core + Memory module map so tier-1 agents get fast orientation.
- **Commits:** see `git log` for the SHA range — `docs:` (root AGENTS.md enhancement) + `docs(review):` (this report) + `chore(context):` (memory bookkeeping: tasks/current, agents/sessions, system/ai-models, system/environments, inefficiencies/log, overrides/rules).
- **Outcome:** done — research report at `.context/memory/reviews/2026-07-30-context-e2e-research.md`; root `AGENTS.md` enhanced with a "Core + Memory at a glance" section (project-owned doc, not auto-refreshed by `context-sync update`); one `[core-defect]` override logged (`context.schema.json` `coreVersion` drift: JSON says 0.2.0, `core/VERSION` says 0.3.0) for the next `context-sync harvest` to pick up.
- **Open items:** none new — the four backlog items from Session 1 (MVP stages 1–4 + drift monitor; Phase-0 proof; repo/service split decision; README package layout) remain the right next steps; this was a research pass on the `.context/` protocol itself, not on Glyph's product scope.
- **Report:** .context/memory/reviews/2026-07-30-context-e2e-research.md

---
## 2026-07-30 — Session 3
- **Agent:** Super Z | **Model:** glm-5.2 (user-confirmed this session; Session 2 recorded `unknown` per Pitfall #25 — corrected in `system/ai-models.md`) | **Platform:** Z.ai cloud sandbox (Linux, workspace `/home/z/my-project/glyph`) | **Role:** engineer | **Core:** 0.3.0
- **Task:** Research Glyph itself (the reverse-engineering toolkit) — the actual target Session 2 missed. Pressure-test RESEARCH.md + ADR-1 against real online research; resolve the open questions (§11); scope the Phase-0 proof (§9) concretely.
- **Commits:** 3 — `docs:` (RESEARCH-DEEP-DIVE.md, the main deliverable) + `docs(review):` (Rosetta prior-art report + this session report) + `chore(context):` (Session 3 memory bookkeeping: ai-models glm-5.2 correction, environments update, sessions append, inefficiencies append, tasks/current cleared). See `git log` for the SHA range.
- **Outcome:** done — `RESEARCH-DEEP-DIVE.md` at repo root (76 KB, 612 lines, 11 sections); 5 parallel online-research clusters ran (capture+schema+codegen, Rosetta prior art, mobile+native+JS RE, bot-mgmt+payments, competitive landscape — ~13k words of verified research output total); Rosetta validated as novel-as-combination (closest prior art: *Carving UI Tests* ICSE 2023); 4 of 5 RESEARCH.md §11 open questions resolved (repo/service split, catalog store, mobile CI vs device, InjectX handoff deferred to user, naming deferred); Phase-0 proof scoped concretely (~2–3 weeks, stages 1–4 only); Kenya-priority finding: M-Pesa Daraja does not sign callbacks (first-class verification recipe opportunity).
- **Open items:** M1 (RESEARCH.md §6b JA3→JA4 wording) + M2 (§11 InjecX→InjectX typo) — recommended in deep-dive §9 but left for user approval (RESEARCH.md is the user's canon); N1 (InjectX handoff catalog field) deferred to user; §4.9 research follow-ups (read Carving-UI-Tests PDF, demo Akto/Levo/Salt). The four backlog items from Session 1 stand, now with concrete scope.
- **Report:** .context/memory/reviews/2026-07-30-glyph-research.md

### Correction (2026-07-30, same session)

The Session 3 entry above (and Session 2's entry) recorded commit SHAs that
were authored as `Z User <z@container>` — the sandbox's default git identity —
instead of `Tisone Kironget <tisonkironget@gmail.com>` (the project's Git
identity per `.context/kickoff.md` Project Facts). I skipped Step 2's
`git config user.name`/`user.email` lines in both sessions. The user caught
it after Session 3.

Fix applied this same session: set the correct identity locally, rewrote
author + committer on the 6 wrong commits with `git filter-branch`, force-
pushed with `--force-with-lease`. The old SHAs are now stale; the corrected
SHAs are:

| Old (stale) | Corrected | Message |
|---|---|---|
| 52f76c5 | e1689d9 | docs: add Core + Memory at-a-glance section to root AGENTS.md |
| 944d010 | 586cc67 | docs(review): .context E2E research — core 0.3.0, core+memory modules |
| c38cb37 | 7db56e6 | chore(context): log Session 2 + record core-defect override |
| 43ee45f | b3ed937 | docs: add RESEARCH-DEEP-DIVE.md — Glyph research companion (Session 3) |
| a0b97b7 | 3feaa7c | docs(review): Rosetta prior-art research + Session 3 report |
| 211e816 | 4cfcd7e | chore(context): log Session 3 + correct model to glm-5.2 |

`origin/main` now shows all 8 commits as `Tisone Kironget <tisonkironget@gmail.com>`.
The protocol gap that let this happen is logged in `flaws/log.md` (marked
`Upstream: candidate` — Step 2 should mark the git-config lines as critical
and a pre-commit quality gate should verify `git config user.email`). See
also `inefficiencies/log.md` 2026-07-30 (Session 3, correction) for the
full root-cause + fix narrative.

---
## 2026-07-30 — Session 4
- **Agent:** Claude Code | **Model:** claude-opus-4-8 | **Platform:** bao@local macOS (Darwin 24.6.0) | **Role:** engineer | **Core:** 0.3.0
- **Task:** Build the general-purpose Glyph base system (user directive: "build everything, general-purpose tool not for specific target, remove injectx framing"). Shift the project from research to build.
- **Commits:** 12 (`f4b4a9c`..`ed5e144`) — `chore(context)` build-mode shift + ADR-2/ADR-3; `docs` InjectX removal; 8 `feat`/`test`/`docs` commits building the package; `docs(review)` report. (Then this `chore(context)` bookkeeping commit.)
- **Outcome:** done — `glyph-re` package built end-to-end: 10 pipeline stages as subpackages over a shared SQLite catalog + `glyph` CLI, **32 passing tests**, console script installs (`pip install -e .`). Pure-stdlib base; mitmproxy/Playwright/genson/duckdb are optional extras. ADR-2 (monorepo architecture) + ADR-3 (Glyph standalone, supersedes ADR-1's InjectX clause) recorded. Two bugs fixed mid-build (single-sample enum gap; auth signing-param false positive).
- **Open items:** HITL review UI, DuckDB backend, Splink/positional Rosetta depth, live-capture E2E run, Daraja recipe — all in `tasks/backlog.md`. Phase-0 proof item is effectively subsumed (the pipeline it would have proven now exists); a real authorized-target run is the natural next validation.
- **Report:** .context/memory/reviews/2026-07-30-build-base-system.md

---
## 2026-07-30 — Session 5
- **Agent:** Claude Code | **Model:** claude-opus-4-8 | **Platform:** bao@local macOS (Darwin 24.6.0) | **Role:** engineer | **Core:** 0.3.0
- **Task:** Continue the build. User deferred the 3.13/Pydantic retarget and real-world validation (both in Session 4's follow-ups), so built the highest-value item within the kept 3.9/dataclasses/stdlib architecture: the human-in-the-loop (HITL) review workflow for Rosetta's low-confidence rows.
- **Commits:** 4 — `chore(context)` (set Session 5 task) + `feat(review)` (the workflow, rebased to `7b1100a` after a concurrent push) + `docs(review)` (report) + this `chore(context)` bookkeeping.
- **Outcome:** done — `glyph.review` module + `glyph review` CLI (interactive + `--auto-confirm` + single-entry `--id/--reject/--set` + `--stats`); `review_state` column with an additive migration; human decisions are ground truth and survive Rosetta re-runs (upsert skips reviewed rows); rejected rows hidden from output. **45 tests pass** (was 32; +13). A concurrent push (`c69fd06`, the user's own RESEARCH-DEEP-DIVE.md edit) landed mid-session — resolved with a clean rebase, no work lost.
- **Open items:** real-world validation now unblocked by this workflow (still deferred by user); 3.13/Pydantic retarget deferred; DuckDB, Splink/positional Rosetta depth, live-capture E2E, Daraja recipe, optional Label Studio surface — all in `tasks/backlog.md`.
- **Report:** .context/memory/reviews/2026-07-30-hitl-review-workflow.md

---
## 2026-07-30 — Session 6
- **Agent:** Super Z | **Model:** glm-5.2 | **Platform:** Z.ai cloud sandbox (Linux, workspace `/home/z/my-project/glyph`) | **Role:** engineer | **Core:** 0.3.0
- **Task:** Tackle backlog. After I scoped the 8 open items and asked which target for the real-world-validation group, the user directed a live capture (uploaded a HAR, then said "actually you can initiate .venv and run live capture"). Ran the full pipeline against a real target.
- **Commits:** 4 — `feat(scripts)` (live_capture_run.py + extract_fixture.py + .gitignore) + `test:` (test_real_world.py + linebet_contacts.json fixture) + `docs(review):` (this report) + this `chore(context):` bookkeeping.
- **Outcome:** done — 3 backlog items closed (Phase-0 proof, Live-capture E2E, Real-world validation). `playwright install chromium` succeeded in the sandbox; `glyph.capture.driver.capture_url` ran live against linebet.com/en/line/basketball (20 flows / 17 endpoints / 1 DOM page); `infer_all` flagged 115 enum candidates; `build_dictionary` decoded **104 entries, 99 high-confidence**. Spot-checks match hand-analysis (`templateType=14`→Facebook, `13`→Instagram, `9`→Telegram, `17`→X, `3`→Security department, `6`→Queries and suggestions, `1`→CUSTOMER SUPPORT). Locked in as `tests/test_real_world.py` (12 integration tests, kept separate from the unit suite) against `tests/fixtures/real/linebet_contacts.json` (real payload, contact values redacted, code→label structure preserved). **57 tests pass total** (was 45; +12). Honest caveats: capture was shallow (partial block interstitial; sibling strategy carried it, DOM-attribute strategy barely fired because the SPA hadn't fully rendered); decodings are from the contacts/config endpoint, not the betting markets. Deeper capture + DOM-strategy validation is the follow-up.
- **Open items:** DuckDB backend, Rosetta depth (Splink + positional/value-inferred — more relevant now given the DOM-strategy caveat), Daraja recipe, Python 3.13 + Pydantic retarget (needs user decision; 3.13 venv not installable in this sandbox), optional Label Studio surface. New follow-up: deeper live capture with page interaction to reach the betting-events API.
- **Report:** .context/memory/reviews/2026-07-30-real-world-validation.md


---
## 2026-07-30 — Session 7
- **Agent:** Super Z | **Model:** glm-5.2 | **Platform:** Z.ai cloud sandbox (Linux, workspace `/home/z/my-project/glyph`) | **Role:** engineer | **Core:** 0.3.0
- **Task:** Proxied live capture (geo-blocked target) + the three corrections the user flagged mid-session: (1) fix the capture filter to capture ALL API traffic (was dropping /LineFeed/ and other script-typed/beacon/websocket surfaces); (2) stop using bash for non-trivial work, persist scripts under /home/z/my-project/scripts/ and run the files (Rule 9); (3) stay in .context compliance.
- **Commits:** `feat(capture):` (1c9f242 — capture-all + websocket + target-agnostic exploration + language-code integration test, pushed via persisted commit script) + this `chore(context):` bookkeeping + a `docs(review):` report.
- **Outcome:** done — three capture-driver improvements landed (capture-all took linebet from 99→466 flows; websocket frame capture added; target-agnostic `explore=N` scroll+click surfaced /en/live + deep league pages). The user's geo-permitted proxy (bore.pub tunnel to their Windows machine) bypassed the geo-block; the proxied capture decoded 100 entries, 90 high-conf, including the full 60-language code→name dictionary (locked in as `tests/test_real_world_languages.py`, 12 tests) and the reference strategy firing on real data (`folderId=1 → "Casino + Games"`). **69 tests pass** (was 57). Honest caveats: /LineFeed/ specifically wasn't reached (likely a websocket that didn't fire on this page-load path — 0 WS frames captured despite the new handler); some sibling_prefix decodings are misfires (correctly flagged for review); the proxy password is in the chat transcript — user must rotate it.
- **Open items:** reach /LineFeed/ (navigate to /en/live + inspect the betting bundle for the WS URL); tighten sibling-prefix strategy (concrete failing cases now exist); DuckDB backend; Daraja recipe; Python 3.13 + Pydantic retarget (needs user decision); optional Label Studio surface.
- **Report:** .context/memory/reviews/2026-07-30-proxied-capture.md


---
## 2026-07-31 — Session 8
- **Agent:** Super Z | **Model:** glm-5.2 | **Platform:** Z.ai cloud sandbox (Linux, workspace `/home/z/my-project/glyph`) | **Role:** engineer | **Core:** 0.3.0
- **Task:** (1) Commit the Session 7 bookkeeping stranded when S7 broke mid-write. (2) Sync the .context core per kickoff Step 1 (verify + status + update if newer).
- **Commits:** `fcaa58d` (S7 bookkeeping — `chore(context): log Session 7 + capture-all report`) + this `chore(context):` bookkeeping + the `docs(review):`-bound report.
- **Outcome:** done — (1) S7 bookkeeping committed + pushed (append-only + secret-scan clean). (2) Sync: `verify` OK (0.3.0); cloned the package upstream (`github.com/TisoneK/.context.git`) as a sibling via persisted script; `status` revealed the **project (0.3.0) is ahead of the package upstream (0.2.0)** — the 0.3.0 "harvest release" was developed in this project but never pushed to the package. `context-sync update` correctly refused to downgrade. No core update applied. The divergence is logged as a flaw (protocol has no project-ahead-of-package behavior + no `publish` command). Action for the user (package maintainer): push the 0.3.0 release to the package upstream.
- **Open items:** push 0.3.0 to the package upstream (user); the flaw will only flow upstream via `harvest` once the package is at 0.3.0+ (chicken-and-egg). Remaining backlog unchanged (DuckDB, Daraja, 3.13+Pydantic, Label Studio, reach /LineFeed/, tighten sibling-prefix).
- **Report:** .context/memory/reviews/2026-07-31-context-sync.md


### Update (2026-07-31, same session — 0.4.0 sync landed)

The 'Outcome' above said 'no core update applied' — that was true at the
time (the package upstream was 0.2.0, project was 0.3.0, update refused
to downgrade). The user then pushed 0.4.0 to the package upstream and
said 'you can now sync.' Re-ran the sync:

- Refreshed the package clone (PAT-authed fetch, PAT stripped after).
- `context-sync status` now reported: source 0.4.0 — UPDATE AVAILABLE
  (same MAJOR: safe to 'update').
- `context-sync update` replaced .context/core/ (whole-tree, memory
  untouched) — 0.3.0 -> 0.4.0. Verify passed.
- Committed as `e19ef89` `chore(context): update core to 0.4.0` + pushed.

0.4.0 is 'the Windows release' — adds `core/bin/context-sync.ps1`
(PowerShell port) so Windows agents can run session commands. Relevant
to the user's Windows/3.13 preference. The update also changed
`templates/kickoff.md` materially (added Windows PowerShell instructions
to the Entry Steps); .context/kickoff.md regenerated from the new
template with Project Facts preserved (this commit). The root AGENTS.md
template did NOT change, so no regen needed there.

The 'project ahead of package' flaw logged earlier (flaws/log.md S8) is
now RESOLVED for this project — the package is at 0.4.0, the project is
at 0.4.0, sync direction is package -> project again as designed. The
flaw itself (protocol has no project-ahead-of-package behavior) remains
open for the package to address.

---
## 2026-07-31 — Session 9
- **Agent:** Claude Code | **Model:** claude-opus-4-8 | **Platform:** bao@local macOS (Darwin 24.6.0) | **Role:** engineer | **Core:** 0.4.0
- **Task:** Live-capture test on the local Mac; then, per user direction, make live browser capture a first-class, site-agnostic CLI command so no per-site scripts are needed.
- **Commits:** 1 feat (`glyph capture live` / `run live` + driver resilience + 5 tests + README) — see `git log`. Plus this bookkeeping commit.
- **Outcome:** done. Live Playwright capture verified locally through the user's bore.pub proxy: **919 flows / 855 endpoints / 1309 decoded** against linebet.com/en/line/basketball (rich — the proxy got past the block interstitial the cloud hit). Wired the driver into the CLI: `glyph capture live <url>` and `glyph run live <url>` — site-agnostic, captures all resource types + WebSocket frames + DOM, target-agnostic explore rounds, `--proxy`/`GLYPH_PROXY`. Made the driver resilient (nav failure persists partial capture + surfaces a clean error instead of a traceback). Deleted the throwaway scratch scripts. 74 tests pass. **mitmproxy live comparison could NOT run here** — the sandbox classifier blocks running a local proxy that upstreams to an authenticated external tunnel (tried twice, did not bypass). Gave the user a grounded architectural comparison instead (Playwright superior for web/DOM targets; mitmproxy's edge is mobile/native no-DOM clients — complementary).
- **Open items:** mitmproxy-vs-Playwright *live* head-to-head needs the user to allow `mitmdump` or run it themselves; verify whether the driver's WebSocket capture stores frame payloads vs just handshakes; bore.pub tunnel is ephemeral (dropped mid-session) — refresh before re-running the linebet capture.
- **Report:** none (feature session; this entry + commit message carry it).

---
## 2026-07-31 — Session 10
- **Agent:** Claude Code | **Model:** claude-opus-4-8 | **Platform:** bao@local macOS (Darwin 24.6.0) | **Role:** engineer | **Core:** 0.4.0
- **Task:** Build the `glyph.sensitive` stage — flag sensitive data, sensitive endpoints, and passive risk indicators. (User asked if Glyph flags sensitive/vulnerable endpoints + sensitive data; it did not. Corrected an early wrong instinct: for an RE tool, FLAG-AND-LOCATE and keep values intact — redaction is opt-in export only, never a default that mutates captured data.)
- **Commits:** 1 feat (glyph.sensitive: detectors + endpoints + risk + findings table + `glyph sensitive` CLI + 14 tests) + this bookkeeping. See `git log`.
- **Outcome:** done. New modular stage: detectors (PII/secrets/financial incl. Kenyan/M-Pesa + Luhn cards + entropy-gated secrets), path-based endpoint classification, and passive risk indicators (secrets-in-URL, unauthenticated-sensitive-data, wildcard CORS, missing security headers, verbose errors, guessable-id IDOR). Catalog `findings` table (kept value, idempotent re-scan). **88 tests pass.** Verified live on demoblaze: flagged `demo@blazemeter.com` + missing security headers on a real capture. Passive only — no active scanning/exploitation.
- **Open items:** live test to exercise `glyph sensitive` against a richer real target (in progress); consider tightening enum deny-list (`desc`/`img`, noted Session 9); optional redacted-export command.
- **Report:** none (feature session; commit + this entry carry it).


---
## 2026-07-31 — Session 11
- **Agent:** Claude Code | **Model:** claude-opus-4-8 | **Platform:** bao@local Windows 10/11 (PowerShell 7) | **Role:** engineer | **Core:** 0.4.0
- **Task:** Setup the local Windows development environment — create venv, install glyph-re[dev], install Playwright Chromium, run baseline tests.
- **Commits:** 3 — `0934faa` (chore(context): add .gitattributes to preserve LF line endings in core/) + `7e64db1` (chore(context): roll back core to 0.4.0) + this bookkeeping.
- **Outcome:** done — `.venv` created with Python 3.14.2, `glyph-re[dev]` installed (mitmproxy 12.2.3, playwright 1.61.0, genson 1.4.0, duckdb 1.5.5, pytest 9.1.1), Playwright Chromium downloaded, **93 tests pass** (1 skipped). Discovered and resolved a Windows CRLF line-ending mismatch in `.context/core/` that caused `context-sync verify` to fail (core files checked out with CRLF due to `core.autocrlf=true`, but MANIFEST.sha256 hashes are computed against LF-only blobs). Fixed by adding `.gitattributes` (`.context/core/* text eol=lf`) and using `git checkout -- .context/core/` to restore LF blobs from git history.
- **Open items:** none — environment is ready for development work.
- **Report:** none (setup session; this entry carries it).

### Update (2026-07-31, Session 10 cont.) — sensitive hooked into `run` by default
Per user ("shouldn't the sensitive be by default hooked in run live?"), the sensitive/risk
scan now runs automatically at the end of `glyph run live` and `glyph run har` (passive, on
already-captured data), with a one-line summary and a `--no-sensitive` opt-out. Also fixed a
credit-card false positive surfaced by the Juice Shop live test (Luhn-valid ms timestamp) via
a card-network-prefix gate. 90 tests.

### Update (2026-07-31, Session 10 cont.) — first/third-party host scoping
Betika live test (318 flows, Rosetta decoded sub_type_id 60→'1st Half 1x2', 186→'WINNER')
exposed that most sensitive findings were on third-party hosts (GTM, adnxs) — the 2 "criticals"
weren't Betika's. Added first/third-party scoping: capture records the primary target host,
a registrable-domain matcher (eTLD+1 incl. .co.ke) tags each finding's party, and
`glyph sensitive` defaults to first-party (--all/--party/--target to control). Cut Betika's
50 findings to 10 trustworthy first-party ones. `party` column on findings (+migration). 94 tests.

### Correction (2026-07-31, Session 10 cont.) — de-noise by tracking-vendor, not third-party
User pushback: hiding third-party findings is wrong — sites store their own data on third-party
CDNs/stores (S3, storage.googleapis.com). Reworked the default: sensitive-data findings are never
hidden on any host; only hygiene chatter (CORS/headers) on KNOWN tracking/ad vendors (GTM,
DoubleClick, adnxs, Hotjar, Clarity...) is noise; CDNs/object stores are explicitly NOT vendors.
Findings now carry host; is_noise() drives the default. On Betika this restored the
storage.googleapis.com CDN data finding that was wrongly hidden. 95 tests. Lesson: don't conflate
"third-party host" with "irrelevant" — the axis is data/behavior vs tracking-hygiene noise.

### Fix (2026-07-31, Session 10 cont.) — reference-join scoped to registrable domain
Flashscore live test (528 flows, 9 websockets) exposed a real Rosetta bug: reference-join used a
GLOBAL id->name index, so a sports eventStageId=12 resolved to a cookie-consent purposeId=12
("Selection of personalised content") from cookielaw.org — cross-host integer-id collision.
Fixed universally: index keyed by registrable domain; ids resolve within their own site only.
Moved registrable_domain to catalog.normalize (shared with rosetta; party re-exports). Verified
on flash.db: 0 cross-domain consent decodings after a clean re-decode. 97 tests. Also noted:
flashscore.com data also served from lsapp.eu (Livesport backend) — related-org domains won't
cross-join (conservative, acceptable). Lesson: single-host test fixtures hid a cross-host bug.

---
## 2026-07-31 — Session 12
- **Agent:** Claude Code | **Model:** claude-opus-4-8 | **Platform:** bao@local macOS (Darwin 24.6.0) | **Role:** engineer | **Core:** 0.4.0
- **Task:** Implement ADR-5 (written proposed by Session 11 on the Windows box) — split the 517-line `glyph/cli.py` into a `glyph/cli/` package, fix the dict/run empty-state messaging, and give `glyph sensitive` real table output.
- **Commits:** 2 — `feat(cli)` (the split + UX fixes) + this `chore(context)`. See `git log`.
- **Outcome:** done. `glyph/cli/` = one module per subcommand (each `add_parser`+`run`) + `_shared`/`_output`/`_format` helpers; `__init__` builds the parser by iterating command modules, `__main__` keeps `python -m glyph.cli`. Business logic untouched (stage packages remain the source of truth). `dict` now distinguishes empty-catalog / rosetta-not-run / rosetta-ran-nothing (new `rosetta_ran` meta flag; added generic `Catalog.get_meta/set_meta`). `glyph sensitive` renders a masked table (`prefix***suffix`, location, severity, party, host); `--json` still returns full raw values (values kept at rest per ADR-4). ADR-5 marked implemented/accepted. **97 tests pass.**
- **Open items:** the ADRs the user flagged as missing are NOT yet written — a capture-scope ADR (HTTP/HAR level vs raw packet `.cap`/pcap) and a mobile-package ADR (APK/IPA static mining; XAPK/split-APK + OBB handling). Also all Session 10 sensitive-stage follow-ups in `tasks/backlog.md`.
- **Report:** none (this entry + ADR-5 carry it).

### Update (2026-07-31, Session 12) — ADR-5 polish (the actual point)
User clarified ADR-5's intent was beauty/intuition, not just the package split. Added TTY-aware
color to `glyph/cli/_format.py`: severity color-coding (critical/high/medium/low) shared across
the sensitive table, run summary, and counts; ANSI-aware table alignment; bold labels/headers,
dim separators/hints; cyan paths/hosts; green success lines. Auto-off on non-TTY/NO_COLOR/--json
so pipes and tests stay plain. 97 tests. Lesson: implement the *user-visible* intent of a UX ADR,
not only its structural half.

---
## 2026-07-31 — Session 13
- **Agent:** Claude Code | **Model:** claude-opus-4-8 | **Platform:** bao@local macOS (Darwin 24.6.0) | **Role:** engineer | **Core:** 0.4.0
- **Task:** Online research (user asked) to ground two scope ADRs the user flagged as missing — capture layer (.cap/pcap vs HTTP/HAR) and mobile packages (XAPK/APKS/APKM/split-APK/OBB).
- **Commits:** 2 — `docs(review)` (research note w/ sources) + this `chore(context)` (ADR-6, ADR-7, backlog, session).
- **Outcome:** done. Researched via WebSearch/WebFetch (mitmproxy has no native pcap I/O; pcap→HTTP needs reassembly+TLS-keylog+parsing and pyshark can't cleanly expose decrypted app-data; packet-level only matters for non-HTTP protocols. XAPK/APKS/APKM = zip-of-split-APKs + OBB; endpoint strings live across base dex, split `.so`, and OBB). **ADR-6:** Glyph is HTTP/application-layer; raw packet capture is out of core (optional pcap→Flow adapter if ever needed); non-HTTP binary protocol RE out of scope. **ADR-7:** mobile stage handles the whole package family by recursively unwrapping bundles and mining every inner APK + OBB (static only; no bundletool/adb; AAB + IPA-decryption out of scope). Both have backlog implementation items. Sources in the research note.
- **Open items:** implement ADR-7 (recursive bundle mining) + optional ADR-6 pcap adapter — both in `tasks/backlog.md`; Session 10 sensitive follow-ups still open.
- **Report:** .context/memory/reviews/2026-07-31-capture-mobile-scope-research.md

### Update (2026-07-31, Session 13) — run summary redesign + Windows ANSI
User (on Windows) reported `glyph run live` output still looked bad — a flat wall of lines.
Redesigned it into one aligned, color-coded block (bold header, cyan labels, bold numbers, dim
resource-type sub-line, severity-colored counts, 'view' footer). Enabled ANSI/VT on Windows
(SetConsoleMode +0x0004) so color renders in PowerShell/conhost — the likely reason Session 11's
output looked plain. Color still auto-off on non-TTY/NO_COLOR/--json. 97 tests. Lesson: verify UX
polish on the user's actual platform (Windows console != a Unix TTY for ANSI).

### Update (2026-07-31, Session 13) — adopt rich for real designed output (ADR-8)
User: hand-rolled ANSI was "still shitty"; wanted real designed tables + a cross-platform package
(colorama or similar). Adopted `rich` as the CLI rendering layer + the package's one runtime dep
(ADR-8): run → rounded panel, sensitive/dict → bordered rich tables with severity color-coding.
rich handles Windows/NO_COLOR/non-TTY itself; library core stays dep-free (rich imported only in
glyph.cli, HAS_RICH fallback). 97 tests. Follow-up: migrate fingerprint/auth/gating/catalog to
rich tables too. Lesson: for polished cross-platform CLI output, use rich — don't hand-roll ANSI.

---
## 2026-07-31 — Session 14
- **Agent:** Claude Code | **Model:** claude-opus-4-8 | **Platform:** bao@local macOS (Darwin 24.6.0) | **Role:** engineer | **Core:** 0.4.0
- **Task:** Build the Glyph TUI dashboard (Phase 1) per the user's detailed spec — an interactive Textual dashboard over glyph.db so `glyph run live` leaves you exploring the captured surface, not reading a report.
- **Commits:** 2 — `feat(tui)` (dashboard + data adapters + dashboard/flows/dom commands + run-live wiring) + this `chore(context)` (ADR-9 + session + task). See `git log`.
- **Outcome:** done (Phase 1). `glyph.tui.data` = pure catalog adapters (unit-tested); `glyph.tui.app` = Textual app (summary header + 5 tabbed DataTables via keys 1-5 + flow request/response drill-in + reload). `glyph dashboard` opens it on any catalog; `glyph run live` opens it when interactive (TTY+textual), else prints the rich summary or `--no-tui`. New `glyph flows`/`glyph dom` table commands. Textual is a `[tui]` extra; engine stays headless (ADR-9). Textual app verified via `App.run_test()` (mounts, tabs switch). **104 tests.**
- **Open items:** Phase 2 = live streaming (driver writes flows incrementally + TUI auto-refresh — needs capture-driver concurrency); DOM harvest under-captures inputs/forms (capture enhancement); migrate fingerprint/auth/gating/catalog to rich tables (ADR-8 follow-up); Session 10 sensitive follow-ups.
- **Report:** none (ADR-9 + this entry carry it).

---
## 2026-07-31 — Session 15
- **Agent:** Claude Code | **Model:** claude-opus-4-8 | **Platform:** bao@local macOS (Darwin 24.6.0) | **Role:** engineer | **Core:** 0.4.0
- **Task:** TUI Phase 2 — live status + real-time data (ADR-9 Phase 2).
- **Commits:** 2 — `feat(tui)` (live) + this `chore(context)`. See `git log`.
- **Outcome:** done. Driver writes flows/WS/DOM incrementally + `capture_status` meta; catalog on WAL+busy_timeout; dashboard live mode runs capture in a worker thread, refreshes flows/DOM/summary every 1s + analysis every 3s, `● LIVE mm:ss` → `✓ captured` header. `glyph run live` opens the live dashboard interactively; `--no-tui`/pipe = synchronous headless path. **107 tests** incl. an async `run_test` proving flows stream 0→N and the header flips. NOTE: the real Playwright browser live path (sync Playwright in a Textual worker thread; two concurrent DB writers under WAL) is implemented but NOT verified on this box (no playwright in `.venv`) — **must be confirmed on the user's Windows machine** (`.venv` there has playwright). Fallbacks: if a worker hits a transient lock, analysis retries next tick; capture writes wait up to busy_timeout.
- **Open items:** verify live browser path on-device; consider resetting the catalog at the start of a live run (currently appends to `--db`); optimize the 1s full-table reload to append-only for large captures; richer DOM capture (inputs/forms); migrate remaining commands to rich tables.
- **Report:** none (ADR-9 Phase 2 note + this entry carry it).

### Update (2026-07-31, Session 15) — home/splash screen + app restructure
Bare `glyph` now opens a home screen (GLYPH gradient wordmark + URL box + Capture/Open/Quit) that
flows into the live dashboard; Esc returns home. Restructured the TUI into `GlyphApp` hosting
`HomeScreen` + `DashboardScreen` (former GlyphDashboard, now a Screen) + `FlowDetail`;
`get_default_screen` picks home vs dashboard. Subcommand optional — bare `glyph` = home (interactive)
or help (pipe). 108 tests (home mount + URL->dashboard covered). Still verify the Playwright browser
live path on the user's Windows box. Lesson: use App.get_default_screen (not on_mount push) so the
initial screen is queryable immediately in run_test.

### Fix (2026-07-31, Session 15) — reset-per-run + live dashboard perf
User's live run showed ALL past targets and hung. Root cause: `run` appended to glyph.db
(accumulation) and the live TUI reloaded all 5 tables every 1s + re-ran full analysis every 3s
with overlapping workers over the huge catalog. Fixes: `Catalog.reset()` at the start of every
run (+ the live capture worker) so a run is fresh per target; live tick refreshes only summary +
visible tab (others on activation); analysis guarded (no overlap) at 4s; final analysis + full
reload then STOP timers when capture done; tables cap at 800 rows. Gotcha: don't name an instance
attr `_timers` on a Textual DOMNode — it shadows Textual's internal timer set (use `_live_timers`).
109 tests.

---
## 2026-07-31 — Session 16 (in progress)
- **Agent:** Super Z | **Model:** unknown (system prompt does not state the exact GLM version; recorded `unknown` per Pitfall #25) | **Platform:** Z.ai cloud sandbox (Linux, Python 3.12.13, workspace `/home/z/my-project/glyph-work/glyph`) | **Role:** engineer | **Core:** 0.4.0
- **Task:** Implement the SNI bug-host hunting feature (ADR-10) — a new `glyph.snihunt` stage
  that discovers NEW SNI bug-host candidates from the live capture via reverse-IP lookup,
  certificate-transparency subdomain enumeration, Cloudflare/CDN frontable-edge detection,
  zero-rating heuristics, and an optional active SNI probe. NOT scraping published bughost.txt
  lists — the user explicitly wants the *process* of finding new hosts. Auto-runs after
  `sensitive` in `glyph run live`/`run har`; new `glyph snihunt` CLI command; new TUI tab
  (key 6, "SNI Hunt").
- **Commits:** (TBD — will fill at session end)
- **Outcome:** (TBD)
- **Open items:** (TBD)
- **Report:** .context/memory/reviews/2026-07-31-sni-bug-host-hunt.md (to be written)
