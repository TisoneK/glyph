# Inefficiency Log (append-only, mandatory)

Every session appends one block — honestly. Friction you absorb silently
is friction the next agent hits blind. "None this session" is valid only
if literally nothing slowed you down.

Most inefficiencies are project-local (an environment quirk, a one-off
cost) and stay here. When one is actually **protocol-level** — the core
workflow itself made you slower and every project would hit it — mark it
`Upstream: candidate`. `context-sync harvest` collects those (and open
`flaws/`) into the package for an upstream fix. Unmarked entries are
never harvested.

<!-- TEMPLATE — copy below the last entry:
---
## YYYY-MM-DD — <agent> / <model>
- **Problem:** <what went wrong or was slower than it should be>
- **Cost:** <rough time/effort wasted>
- **Cause:** <root cause if known>
- **Workaround / fix:** <what worked, or "unresolved">
- **Prevent next time:** <protocol/context change that would have avoided it>
- **Upstream:** candidate  ← add this line ONLY for protocol-level friction
  worth a core fix; omit entirely for project-local friction.
-->

---
## 2026-07-30 — Super Z / unknown
- **Problem:** `context.schema.json` line 5 records `"coreVersion": "0.2.0"` while `core/VERSION` is `0.3.0`. The JSON is documented as a machine-readable mirror of `context-schema.md` and "must be updated in the same commit as any schema change" — but the 0.3.0 release (the harvest release, which added `fleet.md`, `inbox/`, and the `Upstream: candidate` / `[core-defect]` schema fields) did not bump the JSON's `coreVersion` field.
- **Cost:** ~5 minutes of confusion while reading the schema — had to cross-check `core/VERSION` against the JSON to confirm which was authoritative (the markdown schema is authoritative; the JSON is a mirror). Latent risk: any future consumer that trusts the JSON's `coreVersion` (the `$comment` lists "context-sync, future check tooling, agents that prefer structured data") would see the wrong version. In practice `context-sync` reads `core/VERSION` (not the JSON), so the drift is currently documentation-only.
- **Cause:** The 0.3.0 release notes (`core/CHANGELOG.md`) describe the schema-field additions but don't call out a `coreVersion` bump in the JSON. Likely an oversight in the 0.3.0 release commit — the JSON's `coreVersion` was added at 0.2.0 and never updated.
- **Workaround / fix:** No local fix is possible — `core/` is read-only (Binding Rule #2). Recorded as a `[core-defect]` override in `memory/overrides/rules.md` so the next `context-sync harvest` picks it up for an upstream fix in the package repo.
- **Prevent next time:** The 0.3.0 release process should have included a one-line `coreVersion` bump in `context.schema.json`. The package release checklist (not in this repo) should add: "if `core/VERSION` changed, update `context.schema.json`'s `coreVersion` field in the same commit." Suggest the package maintainer add this to the release steps.
- **Upstream:** candidate  ← this is protocol-level friction (the schema's own claim about its mirror is wrong); every project using core 0.3.0 has the same drift. Worth a core fix in a future 0.3.x patch release.

---
## 2026-07-30 — Super Z / glm-5.2 (Session 3)
- **Problem:** Three friction points this session.
  1. **Session 2 mis-targeting (carry-over).** Session 2 researched the `.context/` protocol framework instead of Glyph itself — the user's original target. The user clarified in the Session 3 kickoff ("What I wanted to research is about Glyph not .context!!!"). Session 2's deliverable (`.context/memory/reviews/2026-07-30-context-e2e-research.md` + root `AGENTS.md` enhancement) is still valuable, but it was the wrong primary deliverable for the user's intent.
  2. **Parallel Task agents timed out on large scopes.** Session 3 launched 5 parallel research agents (Tasks 3–7) on the default glm-5.2 model. Tasks 3, 4, 5 completed; Tasks 6 (bot-mgmt + payments) and 7 (competitive landscape) timed out with "context deadline exceeded" — their scope was too large for one tool-call window.
  3. **Write tool JSON-arg length limit.** The 76 KB `RESEARCH-DEEP-DIVE.md` couldn't be written in one Write call (the tool errored on the JSON arg length). Had to split into 3 parts: Write part 1 (§§1-3), then append parts 2 (§§4-6) and 3 (§§7-11) via small Python scripts through Bash.
- **Cost:** ~1 lost session of primary deliverable (Session 2's output is reusable but not what the user asked for); ~15 min recovering from the 2 timed-out agents (re-launched as 3 tighter-scope sub-tasks on the haiku model); ~10 min on the Write-tool length workaround (wrote 2 small Python append scripts).
- **Cause:**
  1. Session 2 read the user's message ("Understand .context E2E then initialize AGENTS.md or kickoff.md (core, memory)") as the primary target, when "core, memory" was a parenthetical specifying which `.context/` modules to focus on — the actual project is Glyph. The `.context/` protocol is the *workflow*, not the *research subject*. **Root cause: ambiguous target in the original message; the agent didn't ask which interpretation was intended.**
  2. The Task tool's parallel agents have a context-deadline budget that large research scopes (especially multi-topic ones like "bot-mgmt + payments" or "competitive landscape across 23 tools") can exceed. The default model (glm-5.2) is capable but slower than haiku for tight research tasks.
  3. The Write tool serializes the file content as a JSON string argument; very long content (≈30 KB+) can exceed the JSON-arg validation limit. This is a tool-level constraint, not a project one.
- **Workaround / fix:**
  1. Session 3 restarted with the correct target (Glyph) and delivered `RESEARCH-DEEP-DIVE.md`. **Prevent next time:** when a user message mentions both a project name and a sub-component (".context E2E ... core, memory"), confirm which is the research subject before starting — the AskUserQuestion tool exists for exactly this. The original Session 2 message was ambiguous enough that a single clarifying question would have saved a session.
  2. Re-launched Tasks 6 and 7 as 3 tighter-scope sub-tasks (6a bot-mgmt, 6b payments, 7 competitive landscape) on the `haiku` model — all completed. **Reusable pattern recorded in `system/environments.md`: keep each parallel research agent's scope narrow enough to finish in one tool-call window; prefer 3–4 small agents over 1 large one; use `haiku` for tight research tasks where `glm-5.2`'s depth isn't needed.**
  3. Wrote `/home/z/my-project/scripts/append_deep_dive_part2.py` and `_part3.py` — small Python scripts that append content to the file via `pathlib.Path.open('a')`. **Reusable pattern recorded in `system/environments.md`: for files >~30 KB, write the first part with Write, append subsequent parts with a small Python script via Bash.** Persist the scripts under `/home/z/my-project/scripts/` (per Rule 9 — Script Persistence) so they're recoverable.
- **Prevent next time:** (1) ask one clarifying question when the target is ambiguous between "the project" and "a sub-component of the project"; (2) default to 3–4 narrow parallel Task agents on `haiku` for online research, not 1 large agent on `glm-5.2`; (3) for any deliverable >~30 KB, plan the multi-part append from the start and persist the append scripts.
- **Upstream:** candidate  ← items 2 and 3 are protocol-level / tool-level friction (the Task tool's context-deadline behavior and the Write tool's JSON-arg limit) that every project using this sandbox will hit. Worth a core fix or a documented pitfall: (a) the protocol's "Common Pitfalls" could add a "parallel Task agents time out on large scopes — split into sub-tasks" entry; (b) the sandbox tooling could lift the Write JSON-arg limit or document the multi-part-append pattern. Item 1 (mis-targeting) is project-local — not harvestable.
