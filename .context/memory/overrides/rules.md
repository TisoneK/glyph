# Protocol Overrides (update in place — project-owned)

Project-local adjustments to the protocol. Sessions read this file
right after loading their edition; where an override and the edition
conflict, **the override wins** — except the two rules nothing can
override: secret handling and append-only guarantees.

Overrides are standing, project-shaped deltas — not session
instructions (those die with the session) and not user preferences
(those live in `../user/preferences.md`). Core updates never touch
this file: customizations here survive every core version bump.

Because they survive core bumps, an override can quietly keep a project
diverged from a core that was later fixed — or diverged from a core that
is *still* broken everywhere else. So tag every override by kind:

- **`[core-defect]`** — core is wrong/broken here and this bullet is a
  local patch. `context-sync harvest` collects these into the package so
  the fix ships in a future core and the next project bootstrapped from
  it never rediscovers the workaround.
- **`[project-local]`** — core is fine; this project just works
  differently (git-flow, house style). Never harvested; stays local.

<!-- TEMPLATE — one bullet per override, tagged by kind, with provenance:
- **[core-defect]** <what core says> → <what THIS project does instead> —
  <why + which core version is broken> (set by <user/agent>, YYYY-MM-DD)
- **[project-local]** <what core says> → <what THIS project does instead> —
  <why this project differs> (set by <user/agent>, YYYY-MM-DD)

Examples:
- **[core-defect]** context-sync verify hashes with `sha256sum` → use
  `certutil -hashfile <file> SHA256`; `sha256sum` isn't on stock Windows
  PATH — core assumes POSIX coreutils (set by agent, 2026-07-20)
- **[project-local]** Push to main after each commit → push to the
  `develop` branch; main is release-only — repo uses git-flow (set by
  user, 2026-07-14)
-->

---

- **[core-defect]** `core/schemas/context.schema.json` declares `"coreVersion": "0.2.0"` while `core/VERSION` is `0.3.0`. The JSON is documented as a machine-readable mirror of `context-schema.md` and "must be updated in the same commit as any schema change" — but the 0.3.0 release (harvest release) did not bump the JSON's `coreVersion` field. Workaround: read `core/VERSION` for the authoritative version (which `context-sync` already does); treat the JSON's `coreVersion` as stale until the package fixes it. The fix belongs in the package repo: bump `context.schema.json`'s `coreVersion` to `0.3.0` in the next 0.3.x patch release, and add "if `core/VERSION` changed, update `context.schema.json`'s `coreVersion` in the same commit" to the package release checklist. (set by Super Z, 2026-07-30; see `memory/inefficiencies/log.md` 2026-07-30 entry for full context)
