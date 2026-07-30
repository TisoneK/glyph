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
