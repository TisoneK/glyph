# Agent + Model Registry (update in place)

Which agents and models have worked on this repo.

| Agent | Model | First seen | Last seen | Sessions |
|---|---|---|---|---|
| Claude Code | claude-opus-4-8 | 2026-07-29 | 2026-07-29 | 1 |
| Super Z | unknown | 2026-07-30 | 2026-07-30 | 1 |

## Observations

- **Claude Code / claude-opus-4-8:** bootstrapped the repo + `.context/` (core 0.3.0) and authored RESEARCH.md (scope, technique catalog, architecture, phasing). (2026-07-29)
- **Super Z / unknown:** system prompt identifies the agent as "Super Z, built on the GLM model developed by Z.ai" but does not state the exact model version. Recorded `unknown` per Pitfall #25 rather than guessing (e.g., `glm-4.6`, `glm-5.2`). Cloud sandbox agent (Linux, `/home/z/my-project/glyph` workspace). Ran Session 2: thorough `.context/` E2E read-through, refreshed root `AGENTS.md` with a Core + Memory module map, logged one `[core-defect]` override (`context.schema.json` `coreVersion` drift). User should fill in the exact model ID if known — future sessions copy it verbatim from the user, never from memory. (2026-07-30)
