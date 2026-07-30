# Agent + Model Registry (update in place)

Which agents and models have worked on this repo.

| Agent | Model | First seen | Last seen | Sessions |
|---|---|---|---|---|
| Claude Code | claude-opus-4-8 | 2026-07-29 | 2026-07-30 | 2 |
| Super Z | glm-5.2 | 2026-07-30 | 2026-07-30 | 2 |

## Observations

- **Claude Code / claude-opus-4-8:** bootstrapped the repo + `.context/` (core 0.3.0) and authored RESEARCH.md (scope, technique catalog, architecture, phasing). (2026-07-29)
- **Claude Code / claude-opus-4-8 (Session 4):** built the general-purpose `glyph-re` package end-to-end — 10 pipeline stages as subpackages over a shared SQLite catalog, `glyph` CLI, 32 passing tests. Recorded ADR-2 (architecture) + ADR-3 (standalone). Worked cleanly with per-stage commits (10 logical commits, each pushed). Ran the suite in a `.venv` on system Python 3.9.6. (2026-07-30)
- **Claude Code / claude-opus-4-8 (Session 5):** added the HITL review workflow (`glyph.review` + `glyph review` CLI + catalog `review_state` migration). 45 tests. Handled a mid-session concurrent push from the user (docs edit to `origin/main`) with a clean `git rebase origin/main` — confirmed zero file overlap first, per the Git Workflow rule. (2026-07-30)
- **Super Z / glm-5.2:** Z.ai cloud sandbox agent (Linux, `/home/z/my-project/glyph` workspace). System prompt identifies the agent as "Super Z, built on the GLM model developed by Z.ai" but does not state the exact version — Session 2 recorded `unknown` per Pitfall #25 (never guess). User confirmed `glm-5.2` in Session 3; corrected here. Ran Session 2 (`.context/` E2E read-through, root AGENTS.md enhancement, one `[core-defect]` override for `context.schema.json` `coreVersion` drift) and Session 3 (Glyph deep-dive research: 5 parallel online-research clusters → `RESEARCH-DEEP-DIVE.md` at repo root, 76 KB / 612 lines / 11 sections; Rosetta prior-art report; resolved 4 of 5 RESEARCH.md §11 open questions; scoped the Phase-0 proof concretely). Observed: parallel sub-task pattern works well for online research — keep each agent's scope narrow (Tasks 6+7 timed out as single large agents on glm-5.2; re-launched as 3 tighter-scope sub-tasks on the haiku model, all completed). (2026-07-30)
