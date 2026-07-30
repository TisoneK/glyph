# Glyph Deep-Dive Research — Session 3 Report

> Session 3 — the actual Glyph research Session 2 was supposed to be. The user
> clarified that the target was Glyph itself (the reverse-engineering toolkit),
> not the `.context/` protocol framework that Session 2 researched by mistake.
> Session 3 restarts with the right target: pressure-test RESEARCH.md + ADR-1
> against real online research, resolve the open questions, and scope the
> Phase-0 proof concretely. Model version corrected to `glm-5.2` (Session 2
> recorded `unknown` per Pitfall #25 — the user supplied the real ID this
> session).

---

## 1. Executive Summary

Session 3 delivered a thorough research companion to RESEARCH.md:
**`RESEARCH-DEEP-DIVE.md`** (76 KB, 612 lines, 11 sections) at the repo root.
The deep-dive pressure-tests every claim in RESEARCH.md against real online
research (2025–2026 sources), verifies every named tool for current version +
license + maintenance, checks the Rosetta centerpiece for prior art, maps the
competitive landscape, resolves four of five open questions (§11), and scopes
the Phase-0 proof concretely.

Five parallel online-research clusters ran (3 completed on the first pass, 2
timed out and were re-run as 3 tighter-scope sub-tasks with the faster haiku
model). All clusters produced verified findings with primary-source URLs. The
raw research notes are archived under `.context/memory/reviews/` (Rosetta
prior art) and `/home/z/my-project/tool-results/` (the other four clusters).

**Three substantive findings change the picture from RESEARCH.md:**

1. **Rosetta is genuinely novel — as a combination.** Every individual half
   exists (Playwright Trace Viewer gives API+DOM pairing for free; genson
   infers schemas; Fellegi-Sunter scores record linkage; Label Studio handles
   HITL review). But no published tool or paper derives code→meaning
   dictionaries by treating the rendered UI as semantic ground truth. The
   single closest published work — *Carving UI Tests* (Yandrapally et al.,
   ICSE 2023) — stops at structure. Recommended positioning pivot: "semantic
   decoding layer over Playwright-Trace-Viewer paired captures, Fellegi-Sunter
   scoring, Label-Studio HITL review."

2. **The APK miner is greenfield.** No existing OSS tool emits a Glyph-style
   endpoint catalog + signing-logic extraction from an APK. MobSF (21.2k★,
   GPL-3.0) is the nearest neighbor but stops at security scoring — drive as
   subprocess (GPL blocks embedding). Android stack (apktool + jadx + apk-mitm
   + Frida) is fully headless/CI-friendly; iOS needs a jailbroken device.

3. **The competitive landscape has three close neighbors, none of which do
   what Glyph does.** Akto (OSS, MIT) — closest on capture→catalog→schema,
   stops there. Levo.ai (commercial, eBPF) — closest commercial, only sees
   your own traffic. MobSF — closest on APK-miner, stops at security findings.
   No published tool combines the full pipeline. Two novelty risks to monitor:
   Salt Security's opaque "business-logic learning" ML, and Cloudflare's ML
   API Discovery + Schema Learning (cite defensively).

**Kenya-specific finding:** M-Pesa Daraja does not sign its callbacks —
anyone with the CallBackURL can POST a fake payment notification. A first-class
"Daraja callback verification" recipe (out-of-band STK-query + idempotent
short-code matching) is a concrete early differentiator for §6g.

---

## 2. Discovery Phase

### Repo state at session start
- Pulled `origin/main` (already up to date at `c38cb37` — Session 2's last
  commit).
- Core integrity: `sh .context/core/bin/context-sync verify` → OK (0.3.0).
- Core drift: `status` → no source reachable (fine per protocol).
- Date: `date -u +%F` → 2026-07-30.

### What was read
- `RESEARCH.md` (full — the canon, 305 lines).
- `.context/memory/plans/decisions.md` (ADR-1, latest text after the
  `62b06ae` scope correction).
- `.context/memory/workflows/active.md`, `tasks/current.md`, `tasks/backlog.md`,
  `agents/sessions.md` (Sessions 1 + 2), `system/ai-models.md`,
  `system/environments.md`, `inefficiencies/log.md`, `overrides/rules.md`.
- Session 2's report (`.context/memory/reviews/2026-07-30-context-e2e-research.md`)
  — to understand what was already done and avoid redoing it.

### Online research (5 clusters, parallel)
| Cluster | Task ID | Status | Output |
|---|---|---|---|
| Capture + schema inference + codegen | 3 | done (glm-5.2) | `/home/z/my-project/tool-results/task3/capture_schema_codegen_research.md` (~1.5k words) |
| Rosetta prior art (UI↔API correlation) | 4 | done (glm-5.2) | `.context/memory/reviews/2026-07-30-rosetta-prior-art.md` (~1.9k words) |
| Mobile + native + JS RE tools | 5 | done (glm-5.2) | `/home/z/my-project/tool-results/task5/js_native_mobile_re_research.md` (~2.4k words) |
| Bot-management landscape (sub-task of 6) | 6a | done (haiku, retry) | `/home/z/my-project/tool-results/task6a/bot-management-research.md` (~2.2k words) |
| Payment integration surfaces (sub-task of 6) | 6b | done (haiku, retry) | `/home/z/my-project/tool-results/task6b/payments-research.md` (~2.0k words) |
| Competitive landscape | 7 | done (haiku, retry) | `/home/z/my-project/tool-results/task7/competitive-landscape-research.md` (~2.8k words) |

Tasks 6 and 7 initially timed out (context deadline exceeded) as single
large agents on the default model. Re-launched as three tighter-scope
sub-tasks on the faster haiku model — all completed successfully. The
parallel approach with sub-tasks is the right pattern for future research
sessions: keep each agent's scope narrow enough to finish, run them in
parallel, synthesize the results in the main agent.

---

## 3. Baseline Health

- **Core integrity:** OK (0.3.0, verified 2026-07-30).
- **Build/test/lint:** N/A — still research-phase, no product code.
- **Memory consistency:** Sessions 1 + 2 entries intact; ai-models registry
  had Super Z / `unknown` (Session 2) — corrected to `glm-5.2` this session
  per the user's confirmation.
- **Two-surfaces rule:** this session touched only the project surface (the
  new `RESEARCH-DEEP-DIVE.md` at the repo root + the Rosetta prior-art
  report under `.context/memory/reviews/`). All commits use `docs:` or
  `docs(review):`. The `chore(context):` commit is for memory bookkeeping
  only (Session 3 entry, ai-models correction, environments update,
  inefficiency log, tasks/current cleared).

**Verdict:** baseline healthy. Nothing to fix.

---

## 4. Findings (by severity)

### Critical
None.

### High
None.

### Medium

**M1 — RESEARCH.md §6b says "JA3/JA4" but JA4 is the current standard.**
- **Description:** RESEARCH.md §6b mentions "JA3/JA4" fingerprinting. JA3
  (Salesforce, 2017) has been superseded by JA4/JA4+ (FoxIO, 2023) — JA4
  leaves the ClientHello fields unhashed (human-readable), and JA4H adds
  HTTP/2 SETTINGS + header order. Cloudflare rolled JA4 out enterprise-wide
  Aug 2024.
- **Impact:** Low — RESEARCH.md is the canon and isn't wrong, just slightly
  dated. Future agents reading it might assume JA3 is the primary fingerprint.
- **Recommendation:** update RESEARCH.md §6b to "JA4/JA4+ (JA3 retained for
  backward compat)." **Not done in this session** — RESEARCH.md is the user's
  canon; the deep-dive recommends the change in §9 but leaves the edit for the
  user to approve. (Per `user/preferences.md`: "Naming and scope are the
  user's call.")
- **Status:** recommended in RESEARCH-DEEP-DIVE.md §9, item 7.

**M2 — RESEARCH.md §11 has an "InjecX" typo (ADR-1 spells it "InjectX").**
- **Description:** RESEARCH.md §11 open-question 4 says "InjecX"; ADR-1
  (latest text after `62b06ae`) says "InjectX."
- **Impact:** Trivial — a typo — but consistency matters across the canon.
- **Recommendation:** fix RESEARCH.md §11 to "InjectX." **Not done in this
  session** — same rationale as M1 (RESEARCH.md is the user's canon).
- **Status:** recommended in RESEARCH-DEEP-DIVE.md §9, item 8.

### Low

**L1 — Session 2's `ai-models.md` entry recorded the model as `unknown`.**
- **Description:** Session 2 (the .context E2E research) recorded Super Z's
  model as `unknown` per Pitfall #25 (system prompt didn't state the exact
  version; never guess). The user confirmed this session that the model is
  `glm-5.2`.
- **Impact:** Corrected in this session's `chore(context):` commit — the
  ai-models registry now shows `glm-5.2` with the observation note updated.
- **Status:** fixed.

**L2 — The `context.schema.json` `coreVersion` drift (Session 2's M1) is
still open upstream.**
- **Description:** Session 2 recorded a `[core-defect]` override for the
  `context.schema.json` `coreVersion` field (says 0.2.0, should be 0.3.0).
  The fix belongs in the protocol package, not this project. No update this
  session — the override is in place and will flow upstream on the next
  `context-sync harvest`.
- **Impact:** None locally (documentation-only drift; `context-sync` reads
  `core/VERSION`, not the JSON).
- **Status:** open upstream — no action this session.

### Nice to Have

**N1 — Consider an "InjectX handoff" catalog-entry schema field.**
- **Description:** RESEARCH.md §11 open-question 4 asks where the handoff
  line to InjectX is. The deep-dive (§7.4) recommends defining it as a
  catalog-entry field (`reachability: direct | needs_tunnel | unreachable`
  + optional `tunnel_hint`). Deferred to the user — it's a product-boundary
  decision between two projects.
- **Status:** recommended in RESEARCH-DEEP-DIVE.md §7.4, deferred to user.

---

## 5. Fixes Applied

- **`RESEARCH-DEEP-DIVE.md` (repo root):** new file, 76 KB, 612 lines, 11
  sections. The main deliverable. Sections mirror RESEARCH.md where
  applicable (§4, §5, §6a–§6j, §8, §9, §10, §11) so the two docs cross-
  reference cleanly. Each section opens with a one-line **verdict** (holds /
  holds with caveats / needs revision) so the user can skim. Commit prefix:
  `docs:` (project surface, alongside RESEARCH.md).

- **`.context/memory/reviews/2026-07-30-rosetta-prior-art.md`:** the Rosetta
  prior-art research (Task 4's deliverable, ~1.9k words). Already written by
  the Task 4 sub-agent; committed this session as `docs(review):`. Referenced
  from RESEARCH-DEEP-DIVE.md §4.

- **`memory/agents/sessions.md`:** appended Session 3's entry (date, agent,
  model=`glm-5.2`, platform, role, core version, task, commits, outcome,
  report path).

- **`memory/system/ai-models.md`:** corrected the Super Z row from
  `unknown` to `glm-5.2` (Pitfall #25 — the user supplied the real ID this
  session). Updated the observation note.

- **`memory/system/environments.md`:** updated the Z.ai cloud sandbox block
  — added a Session 3 "last verified 2026-07-30" note and recorded the
  parallel-sub-task pattern (Tasks 6+7 timed out as single large agents on
  the default model; re-launched as 3 tighter-scope sub-tasks on haiku —
  all completed). This is a reusable pattern for future research sessions.

- **`memory/inefficiencies/log.md`:** appended Session 3's friction — (a)
  the initial mis-targeting (Session 2 researched .context instead of Glyph
  — user's clarification was the fix), (b) Tasks 6+7 timing out as single
  large agents and the sub-task-split recovery, (c) the Write tool's JSON-
  arg length limit forcing a 3-part append of RESEARCH-DEEP-DIVE.md via a
  Python script.

- **`memory/tasks/current.md`:** set to Session 3 in-progress at start;
  cleared to idle at end (Step 15).

- **`memory/tasks/backlog.md`:** no new items — the four existing backlog
  items from Session 1 (MVP, Phase-0 proof, repo/service split, README
  layout) remain the right next steps; this session resolved the repo/
  service split (§7.1) and scoped the Phase-0 proof (§8) concretely, so
  those backlog items are now actionable.

---

## 6. Open Items

- **M1, M2** (RESEARCH.md §6b JA3→JA4 wording; §11 InjecX→InjectX typo) —
  recommended in the deep-dive but left for the user to approve, since
  RESEARCH.md is the user's canon.
- **N1** (InjectX handoff catalog-entry field) — deferred to the user
  (product-boundary decision between Glyph and InjectX).
- **§4.9 open items** (read the full Carving-UI-Tests PDF; demo Akto/Levo/
  Salt to confirm the Rosetta gap; pick Splink vs reimplementation; pick
  Label Studio vs fork) — research follow-ups, not blockers.
- **§11.5 naming** — deferred to the user (per `user/preferences.md`).
- The four backlog items from Session 1 stand, now with concrete scope from
  this session's §7 (repo/service split resolved) and §8 (Phase-0 proof
  scoped).

---

## 7. Recommended Next Steps

1. **Read RESEARCH-DEEP-DIVE.md** — it's the synthesis of 5 research
   clusters + the canon pressure-test. Start with §1 (Executive Summary) and
   §9 (Recommendations).
2. **Greenlight the Phase-0 proof** (§8) — pick a target, build stages 1–4
   minimally, verify Rosetta auto-derives the code dictionary. ~2–3 weeks.
   This is the gate for everything else.
3. **Decide on M1/M2** (the two RESEARCH.md edits) — approve or reject.
4. **Decide on the InjectX handoff** (§7.4 / N1) — it's a product-boundary
   call between two projects only the user can make.
5. **Demo Akto, Levo, and Salt Security** before any external novelty claim
   about Rosetta (§4.8) — confirm the gap.
6. **Rotate the PAT** used for this session (ending in `Bzz`). Used as a
   transient env var, stripped from `.git/config` after every push, unset at
   session end — but rotate anyway.

---

## 8. Verification

- **Core integrity:** `sh .context/core/bin/context-sync verify` →
  `core OK: every file matches MANIFEST.sha256 (0.3.0)` — verified
  2026-07-30.
- **Date:** `date -u +%F` → 2026-07-30 — used for all session entries, the
  report filename, and the `verified` field.
- **Append-only diffs:** before committing `agents/sessions.md`,
  `tasks/backlog.md`, `inefficiencies/log.md`, and `flaws/log.md`,
  `git diff <file>` was reviewed to confirm every changed line is `+`
  (Pitfall #39).
- **No secrets in diff:** `git diff` scanned for `x-access-token`,
  `github_pat_`, `ghp_`, `gho_` — all empty (Pitfall #40). Verified the
  actual PAT value is not in any tracked or new file.
- **Two-surfaces rule:** this session touched the project surface
  (RESEARCH-DEEP-DIVE.md + the Rosetta prior-art review) and the memory
  surface (bookkeeping). No product code was modified (there is no product
  code yet). All commits use `docs:` / `docs(review):` / `chore(context):`.
- **Model version:** recorded `glm-5.2` (user-confirmed) — corrected the
  Session 2 `unknown` entry per Pitfall #25.
