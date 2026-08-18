# Agent Instructions — Glyph

<!-- Generated at bootstrap from .context/core/templates/AGENTS.md.
Refreshed on core updates (fill <PROJECT_NAME> again). Optionally also
copied to CLAUDE.md and .github/copilot-instructions.md so tools that
auto-load those paths get the same digest.

The "Core + Memory at a glance" section below was added by Session 2
(2026-07-30) to give tier-1 agents a fast orientation map of the two
zones without first having to read .context/README.md and the schema.
It is project-owned documentation (the root AGENTS.md is NOT auto-
refreshed by `context-sync update` — only .context/README.md is), so
custom additions survive core bumps. If a future core release changes
the zone layout, the file modes, or the fact scopes, regenerate this
file from .context/core/templates/AGENTS.md and re-add the section by
hand. -->

This repo uses the `.context/` protocol: persistent agent memory plus a
vendored copy of the full workflow, committed to git. **Before doing any
work, read `.context/kickoff.md` and follow it.** It routes you — local
IDE agent or cloud/sandbox agent — to the right instruction set in
`.context/core/rules/`.

If you read nothing else, obey these rules:

1. **Start at `.context/kickoff.md`.** Do not treat "start the context
   workflow" as running this project's app, and do not grep the codebase
   for "context" — the protocol lives in the `.context/` directory.
2. **Never write under `.context/core/`** — it is a read-only, versioned
   copy of the protocol. All project memory you write lives under
   `.context/memory/`.
3. **Pick your instruction set by YOUR agent type**, never by what a
   previous session recorded: local IDE agent →
   `.context/core/rules/ai-engineering-protocol-local.md`; cloud/sandbox
   agent → `.context/core/rules/ai-engineering-protocol.md`. Local
   agents never use PATs or clone this repo; cloud steps are not yours.
4. **Read memory before working:** at minimum
   `.context/memory/workflows/active.md`,
   `.context/memory/agents/sessions.md` (last entries),
   `.context/memory/collaboration/README.md` and relevant event files
   when collaboration is enabled, `.context/memory/workflows/gates.conf`,
   `.context/memory/tasks/current.md`, and
   `.context/memory/inefficiencies/log.md` (known traps). If the
   active session has detailed notes at
   `.context/memory/sessions/`, skim them for current state.
5. **Choose the mode explicitly.** Without a shared collaboration
   `session` + `issue`, `tasks/current.md` is the single-agent lock. In
   collaboration mode, use an isolated git worktree/branch and the
   immutable event trail; do not block peers on `tasks/current.md`. Before
   each next action run `context-gates checkpoint`; before commits,
   integration, and exit run the matching gate.
6. **Append-only files are append-only:** `agents/sessions.md`,
   `tasks/backlog.md`, `plans/decisions.md`, `flaws/log.md`,
   `inefficiencies/log.md`. Add at the bottom; never edit or delete
   past entries. Collaboration event files are stronger: immutable,
   one event per file; emit a correction instead of editing one.
7. **No secrets in tracked files, ever.** Values go only in
   `.context/memory/secrets/` (self-gitignored). Never echo a secret or
   token in chat, logs, or commit messages.
8. **Two surfaces, two prefixes:** editing product code = normal commit
   prefixes; editing `.context/` = `chore(context):` (reports:
   `docs(review):`). Never mix both surfaces in one commit. Collaboration
   events are separate immutable context commits.
9. **The session is not done until everything is committed AND pushed**,
   the session is logged in `.context/memory/agents/sessions.md`, and
   `.context/memory/tasks/current.md` is cleared. If the user has to
   remind you to commit or push, that is a protocol failure — log it in
   `.context/memory/flaws/log.md`.
10. **Don't ask permission for the default next step.** Do it and
    report. Ask only on genuine ambiguity or destructive/irreversible
    actions.

Formats and file rules: `.context/core/schemas/context-schema.md` is
the single source of truth. Project-specific rule adjustments:
`.context/memory/overrides/rules.md` (they win over the edition).

---

## Core + Memory at a glance

The `.context/` directory has **two zones**. Memorize the boundary —
it is the entire sync model.

| Zone | Path | Owner | Agents may write? | How it changes |
|---|---|---|---|---|
| **core/** | `.context/core/` | the protocol package | **Never. Not one byte.** | Only via `context-sync update` (whole-tree, version-stamped, memory untouched) |
| **memory/** | `.context/memory/` | this project | Yes — per each file's write mode | Normal session work, committed with the project |

### Zone 1 — `core/` (read-only reference, vendored at version 0.8.0)

```
core/
├── VERSION              # 0.8.0  (semver of this core tree)
├── CHANGELOG.md         # one entry per release + migration notes
├── MANIFEST.sha256      # checksums — `context-sync verify` checks every file
├── bin/context-sync     # POSIX sh, 8 commands (5 project + 3 package)
├── bin/context-collab   # peer coordination + integration checks (opt-in)
├── bin/context-gates    # lifecycle gates: checkpoint / pre-commit / integration / exit
├── rules/               # ai-engineering-protocol.md (cloud) + -local.md (IDE)
├── roles/               # overlays: feature-engineer, reviewer, security-auditor, docs-agent
├── schemas/             # context-schema.md (authoritative) + context.schema.json (mirror)
└── templates/           # AGENTS.md, context-README.md, kickoff.md, memory/ stub tree
```

`context-sync` commands (project mode — run as
`sh .context/core/bin/context-sync <cmd>`):

- `status` — local core version + best reachable update source (sibling clone, `CONTEXT_PKG`, or path arg).
- `verify` — hash every core file against `MANIFEST.sha256`. On success, refresh `memory/core.lock`. On failure (exit 3): `rollback`, log a flaw, continue.
- `update [SOURCE] [--major]` — atomically swap `core/` from a package source. Same-MAJOR is safe; MAJOR needs `--major`. **Never touches `memory/`.**
- `rollback [VERSION]` — restore `core/` from this project's git history (default: the version in `memory/core.lock`).
- `lock` — record the current verified core version in `memory/core.lock`.

A protocol improvement belongs in `memory/flaws/log.md` (it flows
upstream via `context-sync harvest` and comes back in a future core
release) — **never patched into the vendored copy**.

### Zone 2 — `memory/` (this project's living memory)

| Path (under `memory/`) | Mode | Scope | Holds |
|---|---|---|---|
| `agents/sessions.md` | append-only | project | One entry per session: agent, model, task, commits, outcome |
| `tasks/current.md` | overwrite | project | The one task in progress — **the single-agent session lock** |
| `tasks/backlog.md` | append-only | project | Open items for future sessions |
| `plans/decisions.md` | append-only | project | ADR-style decisions — respected, not relitigated |
| `flaws/log.md` | append-only | project→package | Friction with the `.context/` system itself; flows upstream via `harvest` |
| `inefficiencies/log.md` | append-only | project | Friction with the project's code/env/deps. Mark `Upstream: candidate` for protocol-level friction worth harvesting |
| `reviews/YYYY-MM-DD-*.md` | new file per session | project | Session reports — commit as `docs(review):` |
| `workflows/active.md` | overwrite | project | Standing session parameters; protocol recorded "by agent type" (both editions, never one) |
| `workflows/gates.conf` | update-in-place | project | Lifecycle gate command registry (init via `context-gates init`) |
| `system/environments.md` | update-in-place | **machine** | One block per machine, keyed by its "Identify by" line |
| `system/ai-models.md` | update-in-place | **agent-model** | Registry + observations per agent/model |
| `user/identity.md` | update-in-place | user | Who the user is |
| `user/preferences.md` | update-in-place | user | Standing preferences, each bullet with provenance |
| `overrides/rules.md` | update-in-place | project | Project-local protocol adjustments — beat the edition (except secrets/append-only). Tag `[core-defect]` or `[project-local]` |
| `core.lock` | overwrite (by `context-sync` only) | project | Last-known-good core version + when verified |
| `secrets/<slug>` | local-only | machine | One secret per file; line 1 = value. Self-gitignored, never travels |

**Five write modes:** append-only · overwrite · update-in-place · generated · local-only.
**Five fact scopes:** project · agent-type · machine · agent-model · user.

**Scope contamination is the #1 multi-agent failure mode.** Your
edition comes from YOUR agent type at session start — never from
memory. A machine-scoped block applies only where its "Identify by"
matches. PAT steps exist only in the cloud edition; a local agent
that finds PAT instructions in memory ignores them and logs a flaw.
When writing, ask: "would this sentence be wrong for an agent of the
other type, on another machine?" If yes, key it to its scope or don't
write it.

### The three-tier translation layer (how weaker agents consume this)

1. **This file** (`AGENTS.md` at the project root, ~60–100 lines) —
   the floor. An agent that reads nothing else still learns where
   memory lives, what it must never write to, and where to start.
2. **`.context/kickoff.md`** — the front door: typed entry steps that
   route by agent type and point into `core/rules/`.
3. **The full edition in `core/rules/`** — the complete instruction
   set for agents that can hold it (~986 lines cloud / ~976 lines local).

Each tier links down to the next; no tier contradicts another because
all three are rendered from the same core version. A weak agent
following only tier 1 does less, but nothing **wrong** — it cannot
clobber `core/`, cannot miss the entry point, and cannot pick the wrong
edition.

---

## Product context: the catalog is multi-target (ADR-12, Session 18)

The `glyph` catalog (SQLite, `glyph/catalog/store.py`) is **multi-target**.
A `targets` table holds every host ever captured, and every data row
(flows, endpoints, fields, dictionary, page_observations, findings,
vpn_configs) carries a `target_id`. Capturing `betika.com` then
`sportybet.com` leaves BOTH in the catalog, each queryable via
`glyph target show <host>` and filterable via `--target`.

Key invariants a future agent must respect:
- **`set_target(host)` activates; `clear_target()` wipes only that
  target's rows.** A run calls both — it does NOT call `reset()` (that's
  a full wipe, reserved for tests + a future `--reset` flag).
- **Every write stamps a NON-NULL `target_id`** (explicit > active > the
  reserved "(unassigned)" bucket, id=0). This is required: SQLite treats
  `NULL != NULL` in UNIQUE constraints, so nullable `target_id` would
  break upsert dedup.
- **Reads filter to the active target by default** (fall back to "all
  targets" when no target is active). Pass `all_targets=True` to force
  all, or an explicit `target_id` for a specific one.
- **`capture` accumulates; `run` clears.** `glyph capture har/live` adds
  traffic to the active (or unassigned) target; `glyph run har/live`
  activates + clears one target first (fresh analysis).
- The "(unassigned)" target (id=0) is where rows land when no target is
  set (legacy tests, REPL scratch). It's visible in `glyph target list`
  and clearable with `glyph target rm 0`.

Full design + migration notes: `.context/memory/plans/decisions.md` ADR-12,
`.context/memory/reviews/2026-07-31-multi-target-schema.md`.
