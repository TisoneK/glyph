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
