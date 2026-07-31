# .context E2E Research — Core & Memory Modules

> Session 2 — thorough read-through of the `.context/` protocol (core
> 0.3.0) as it is vendored in this repo. Goal: understand the end-to-end
> flow from a fresh clone through a complete session, and surface how the
> **`core/`** and **`memory/`** modules connect, scope, and protect agent
> state. Findings are recorded as a structured reference for any future
> agent (or human) onboarding onto this repo.

---

## 1. Executive Summary

Glyph is a research-phase project: a planned standalone reverse-engineering
toolkit with no product code yet — only `README.md`, `RESEARCH.md`, and the
`.context/` directory. The whole point of this session was to read the
protocol deeply, not to write product code.

The `.context/` protocol is a **two-zone, vendored agent-memory system**
that travels inside a repo. Its design solves four problems observed in the
field:

1. **Stateless agents forget.** Each new session starts blind unless the
   prior session's work, decisions, and traps are persisted in-tree.
2. **Multi-agent contamination.** When local IDE agents and cloud/sandbox
   agents both work on a repo, facts true for one type ("the repo was
   cloned at /home/z/…") get recorded as universal — and the next agent
   of the other type obeys them wrongly.
3. **Protocol drift.** When the workflow itself is improved, every project
   using it must update consistently — without losing per-project memory.
4. **Weak-agent legibility.** Not every agent reads a 986-line edition
   reliably. The system must degrade gracefully.

The protocol solves these with: a checksummed, read-only **`core/`** zone
that updates as a unit; a writable, schema-validated **`memory/`** zone
whose every file declares its write mode and fact scope; a typed
**`kickoff.md`** front door that routes agents by their own type (never by
memory); and a three-tier **translation layer** (root `AGENTS.md` →
`kickoff.md` → full edition) so a weak agent following only tier 1 still
does nothing wrong.

Core version in force: **0.3.0** ("the harvest release"), verified against
`MANIFEST.sha256` at session start (`sh .context/core/bin/context-sync
verify` → OK). No newer core is reachable from this sandbox (no sibling
package clone, `CONTEXT_PKG` unset) — this is fine; the protocol explicitly
says sync must never fail a session.

---

## 2. Discovery Phase — Top-Level Layout

The repo is intentionally minimal at this phase:

```
glyph/
├── .gitignore            # macOS + editor + .env* ignores (10 lines)
├── AGENTS.md             # generated tier-1 digest (root)
├── README.md             # ~25 lines: what Glyph is, points to RESEARCH.md
├── RESEARCH.md           # ~305 lines: scope, techniques, architecture, phasing
└── .context/
    ├── README.md         # the zone map (CORE-OWNED, refreshed on core updates)
    ├── kickoff.md        # the front door (project-owned data)
    ├── core/             # ZONE 1 — vendored protocol, READ-ONLY
    └── memory/           # ZONE 2 — this project's living memory
```

No product code, no tests, no `package.json`/`pyproject.toml`. The
"baseline health" check (Step 8 of the protocol) is therefore a no-op:
nothing to typecheck, lint, or test. The only baseline is the `.context/`
core integrity check, which passes.

### Prior session context (from memory/)

- **Session 1 (2026-07-29):** Claude Code / `claude-opus-4-8` bootstrapped
  the repo — created `~/Code/glyph`, moved it from `~/Desktop`, authored
  `RESEARCH.md` + `README.md` + `.gitignore`, bootstrapped `.context/`
  from core 0.3.0, registered in the package `fleet.md`, pushed 2 commits
  (`55df6da`, `fd1ccf1`).
- **Follow-up commits:** `b66053f` (docs: scope correction —
  characterize → defeat) and `62b06ae` (chore(context): correct ADR-1 to
  scope defeat) — a scope reframe where the user changed Glyph's posture
  from "characterize but never defeat" to "defeats anti-bot/CAPTCHA/access
  controls as a natural consequence of decoding them."
- **Open backlog:** 4 items (MVP stages 1–4 + drift monitor; Phase-0
  proof; repo/service split decision; README package layout). All high/
  medium priority, all deferred until the Phase-0 proof is greenlit.
- **Known traps:** none logged yet in `inefficiencies/log.md` or
  `flaws/log.md` — Session 1 left both empty (bootstrap session).
- **Standing decisions:** ADR-1 (Glyph is a standalone, domain-neutral
  reverse-engineering toolkit; tunneling/relay routing is owned by the
  separate InjectX project).

### Git history (4 commits, all on `main`)

```
62b06ae  chore(context): correct ADR-1 to scope defeat
b66053f  docs: scope correction — characterize -> defeat
fd1ccf1  chore(context): bootstrap .context/ (core 0.3.0)
55df6da  docs: Glyph reverse-engineering research & feature exploration
```

Commit style is Conventional Commits with scope where applicable
(`chore(context):`, `docs:`). `.context/` and product code live in
separate commits — the two-surfaces rule (Binding Rule #3) is already
in force.

---

## 3. Baseline Health

- **Core integrity:** `sh .context/core/bin/context-sync verify` →
  **OK** — every core file matches `MANIFEST.sha256` (33 files, version
  0.3.0). The lock file `memory/core.lock` records `version=0.3.0`,
  `verified=2026-07-29` — consistent.
- **Core drift:** `sh .context/core/bin/context-sync status` → core
  0.3.0, locked 0.3.0, no source reachable. No update needed; no update
  possible from this sandbox. Logged as "fine" per protocol.
- **Build/test/lint:** N/A — no product code yet. The repo is in
  research/exploration phase (per `workflows/active.md` and ADR-1).
- **Memory consistency:** every memory file matches its template; the
  only populated entries are Session 1's bootstrap (sessions.md, the
  environments.md `bao@local (macOS)` block, the ai-models.md Claude
  Code row, ADR-1, and the 4 backlog items). No corruption, no
  scope-leakage observed.

**Verdict:** baseline healthy. Nothing to fix.

---

## 4. The `.context/` E2E Flow — End to End

The protocol describes a closed loop with **five sub-flows**. This
section walks each in the order an agent encounters them, with the exact
files and commands that drive them.

### 4.1 Bootstrap (one-time, package-side)

Bootstrap happens once per repo, from a clone of the **protocol package**
(not the project). It is the only moment any session touches the package
directly. After it, the protocol lives inside the project and travels
with every clone.

```bash
# From the package clone:
sh <package>/core/bin/context-sync bootstrap <project-root>
```

What `cmd_bootstrap` (in `core/bin/context-sync`, lines 249–289) does:

1. Refuses if `<project-root>/.context` already exists — re-bootstrapping
   over an existing `.context/` would clobber a verified core or the
   project's memory (this is Pitfall #33 in the cloud edition).
2. Verifies the package's own core against its manifest — never installs
   a corrupt core.
3. Creates `.context/`, copies `core/` (the whole tree) into
   `.context/core/`, copies `core/templates/memory/` into
   `.context/memory/`, copies `core/templates/context-README.md` to
   `.context/README.md`, copies `core/templates/kickoff.md` to
   `.context/kickoff.md`, and (only if missing) copies
   `core/templates/AGENTS.md` to the project root `AGENTS.md`.
4. Writes `.context/memory/core.lock` with the current version + date
   (the last-known-good marker).
5. Reads the project's `origin` remote URL and **registers it in the
   package's `fleet.md`** (append-only, idempotent on the URL). This is
   what makes the package's `harvest` command able to find this project
   later.
6. Prints next-step instructions for the bootstrapping agent: fill
   `.context/kickoff.md` Project Facts, fill `memory/` (user/,
   workflows/, system/, tasks/, agents/), scan for leftover placeholders,
   commit as `chore(context): bootstrap .context/ (core <version>)`.

The bootstrapping agent then fills memory from the Pre-Flight section of
the protocol edition, configures git identity, and pushes. After that
single push, no future session ever needs package access — the protocol
is on disk inside the project.

### 4.2 Session entry (every session, every agent)

The entry sequence is fully scripted in `.context/kickoff.md` →
"Entry Steps (every session after bootstrap)". Four steps:

**Step 0 — Identify your agent type, get the project on disk.**

This is the contamination-prevention gate. The agent must decide:
am I a **local** agent (already inside the repo, pushing with the
user's own git credentials) or a **cloud/sandbox** agent (empty
workspace, must clone, needs a PAT for any push)?

- Local agents: confirm `git remote get-url origin` matches the
  Project repository URL. **Never re-clone. No PAT, ever.** If a push
  fails with auth, stop and tell the user.
- Cloud/sandbox agents: clone with the PAT embedded in the URL, then
  **immediately strip the token from `.git/config`** (`git remote
  set-url origin https://github.com/...` without the token). Configure
  git identity from Project Facts.

The protocol is emphatic (Pitfall #43): your edition comes from YOUR
agent type at session start, **never from memory**. If
`memory/workflows/active.md` names a single edition, that's the previous
agent's type leaking — ignore it and follow your own type.

**Step 1 — Sync the project, check the core.**

```bash
git pull --ff-only
sh .context/core/bin/context-sync verify    # integrity
sh .context/core/bin/context-sync status    # drift
```

- If pull fails (diverged) or the tree has changes the agent didn't
  make: **stop and report** — never stash or discard someone else's work.
- If `verify` fails: core was hand-edited or corrupted. Run
  `context-sync rollback`, log a flaw in `memory/flaws/log.md`, continue
  on the restored core.
- If `status` reports a newer core with the **same MAJOR**: run
  `context-sync update` (replaces `core/` only, never touches `memory/`),
  commit as `chore(context): update core to <version>`, read the new
  `CHANGELOG.md` entries.
- A **MAJOR** bump, or no update source reachable: note it in the
  session entry and move on. **A session must never fail over sync.**

**Step 2 — Read `.context/`.**

In strict order: `.context/README.md` (zone map) → `memory/workflows/
active.md` → `agents/sessions.md` (last 3–5 entries) → `tasks/current.md`
→ `tasks/backlog.md` → `inefficiencies/log.md` → `flaws/log.md` →
`plans/decisions.md` → `overrides/rules.md` → `system/` → `user/` →
note what's in `secrets/` (never print values).

If `tasks/current.md` shows another live session in progress: **do not
start** — one agent per project repo at a time. `tasks/current.md`
doubles as the concurrency lock.

**Step 3 — Load the protocol.**

Pick the edition by YOUR agent type from the vendored core:
local → `core/rules/ai-engineering-protocol-local.md`; cloud/sandbox →
`core/rules/ai-engineering-protocol.md`. Also read any role overlay from
`core/roles/` and the project's overrides in `memory/overrides/rules.md`
(overrides beat the edition, except secret-handling and append-only
rules). **Read your edition in full** — it is the instruction set for
this session.

**Step 4 — Follow the protocol.** All steps, all phases, in order. Don't
skip Phase 1 because the task seems small. Don't forget the Exit
checklist.

### 4.3 The protocol execution loop (six phases, nineteen steps)

The cloud edition (`core/rules/ai-engineering-protocol.md`, 986 lines)
and the local edition (`-local.md`, 976 lines) share the same six-phase
shape. The differences are confined to Step 1 (PAT vs. no-PAT), Step 2
(clone vs. already-on-disk), and the push workflow (PAT dance vs. plain
push). Every other step is identical.

| Phase | Steps | What happens | Code changes? |
|---|---|---|---|
| **1 Setup** | 1–8 | PAT/clone, read `.context/`, install deps, read docs, fill Agent Discovery, run baseline health | no |
| **2 Review** | 9 | Review across focus areas (or scoped to Target) | no |
| **3 Fix** | 10–12 | Apply safe fixes, commit each, push each | yes |
| **4 Report** | 13–14 | Write `.context/memory/reviews/YYYY-MM-DD-review.md`, update CHANGELOG | no (commit is `docs(review):`) |
| **5 Update memory** | 15–17 | Clear `tasks/current.md`, append backlog, update system/user/plans, log session + inefficiencies + flaws | no (commit is `chore(context):`) |
| **6 Wrap** | 18–19 | Chat summary, unset PAT | — |

Two **binding invariants** run through every phase:

- **Two surfaces, never one commit.** Project code (`fix:`, `feat:`,
  `docs:`) and `.context/` memory (`chore(context):`, except reports
  which are `docs(review):`) are staged and committed separately. Never
  `git add -A` with both dirty (Pitfall #38). Before committing an
  append-only log, run `git diff <file>` and confirm every changed line
  is `+` (Pitfall #39).
- **Append-only is forever.** `sessions.md`, `tasks/backlog.md`,
  `plans/decisions.md`, `flaws/log.md`, `inefficiencies/log.md` never
  lose entries. Corrections are appended; the only exception is
  byte-identical duplicates, which may be removed leaving a one-line
  note.

### 4.4 The sync, update, and rollback loop

`core/bin/context-sync` is a 407-line POSIX `sh` script with **eight
commands** across two modes. Project mode (run as
`sh .context/core/bin/context-sync <cmd>`) has five; package mode (run
from a package clone) has three.

**Project mode:**

| Command | What it does |
|---|---|
| `status` | Prints local core version, the locked version (from `memory/core.lock`), and the best reachable update source (sibling package clone, `CONTEXT_PKG` env var, or a path argument). Classifies the source as `newer` / `same` / `older` and tells you whether `update` is safe (same MAJOR) or needs `--major`. |
| `verify` | Hashes every core file with `sha256sum` (Linux) or `shasum -a 256` (macOS) and compares against `core/MANIFEST.sha256`. On success, writes the current version + date to `memory/core.lock`. On failure, exit 3 and instruct the agent to `rollback` and log a flaw — never "fix" core in place. |
| `update [SOURCE] [--major]` | Refuses to downgrade. Refuses a MAJOR bump without `--major`. Stages the new core in `.context/core.new`, verifies the staged copy, then atomically swaps (unlink-safe: the running script keeps its open inode). Also refreshes `.context/README.md` from the new `core/templates/context-README.md`. **Never touches `memory/`.** |
| `rollback [VERSION]` | Walks `git log -- .context/core/VERSION`, finds the first commit whose `VERSION` matches (default: the one in `core.lock`), and `git checkout`s `.context/core` from that commit. Writes the restored version to `core.lock`. |
| `lock` | Records the current verified core version in `memory/core.lock`. (`verify` and `update` already call this; `lock` is for manual use.) |

**Package mode:**

| Command | What it does |
|---|---|
| `manifest` | Regenerates `core/MANIFEST.sha256` (maintainers, per release). Sorts files with `LC_ALL=C sort` for reproducibility. |
| `bootstrap DEST` | Initializes `DEST/.context/` (vendored core + memory skeleton + root files + `core.lock`). Also registers `DEST`'s `origin` URL in the package's `fleet.md`. |
| `harvest [FLEET]` | Reads every project URL from `fleet.md`, reaches each read-only (prefers a sibling clone matched by remote URL; else shallow-clones into `.harvest-cache/`), and collects three signals into `inbox/harvest-<date>.md`: open `flaws/`, `Upstream: candidate` inefficiencies, and `[core-defect]` overrides. A committed ledger (`inbox/.harvested`) hashes each entry so re-runs never re-file it. **Never writes to the projects.** |

The harvest loop is the **upstream back-channel** — the mechanism that
closes the feedback loop the `flaws/` directory only ever promised. A
project logs a flaw → `harvest` collects it → the package maintainer
triages → the fix ships in a future core release → the next
`context-sync update` brings it back to every project. Without harvest,
flaws would accumulate in each project's `flaws/log.md` and never flow
upstream.

### 4.5 The exit checklist (Step 19 — the session is not done until ALL of these happen)

- All fixes committed AND pushed
- Report written, committed, AND pushed (`.context/memory/reviews/`)
- CHANGELOG updated, committed, AND pushed (if behavior changed)
- `tasks/`, `system/`, `plans/` updated, committed, AND pushed
- `agents/sessions.md` + `inefficiencies/log.md` + `flaws/log.md`
  appended, committed, AND pushed
- `tasks/current.md` cleared (set to idle)
- PAT unset (Step 19, cloud only)
- Chat summary delivered to user

> Per Binding Rule #10: "If the user has to remind you to commit or push,
> the protocol has failed. Log it as a flaw."

---

## 5. Deep Dive — the `core/` Module (Zone 1, read-only)

`core/` is the **vendored protocol package**. It is owned by the package,
not the project. The cardinal rule (Binding Rule #2, schema "coreReadOnly"):
**no agent writes under `.context/core/` in a project repo, ever.** A
protocol improvement belongs in `memory/flaws/log.md` (it flows upstream
via `harvest` and comes back in a core release) — never patched into the
vendored copy.

### 5.1 File inventory (33 files, 0.3.0)

```
core/
├── VERSION                  # 0.3.0  (semver of this core tree)
├── CHANGELOG.md             # one entry per release + migration notes
├── MANIFEST.sha256          # 33 sha256sums — verify checks every file against this
├── bin/
│   └── context-sync         # POSIX sh, 407 lines — 8 commands (5 project + 3 package)
├── rules/
│   ├── ai-engineering-protocol.md         # CLOUD/SANDBOX edition (986 lines)
│   └── ai-engineering-protocol-local.md   # LOCAL/IDE edition (976 lines)
├── roles/                   # mission overlays (5 roles; engineer is the default, no file)
│   ├── README.md                          # how overlays bind
│   ├── feature-engineer.md               # design + build
│   ├── reviewer.md                       # read-only audit
│   ├── security-auditor.md               # security-only deep audit
│   └── docs-agent.md                     # make docs match code
├── schemas/
│   ├── context-schema.md                 # AUTHORITATIVE — every file's mode, scope, ownership
│   └── context.schema.json               # machine-readable mirror (consumers: context-sync, agents)
└── templates/
    ├── AGENTS.md                          # becomes the root AGENTS.md (tier-1 digest)
    ├── context-README.md                  # becomes .context/README.md (zone map)
    ├── kickoff.md                         # becomes .context/kickoff.md (front door)
    └── memory/                            # the memory/ stub tree copied at bootstrap
        ├── core.lock                      # template for memory/core.lock
        ├── agents/sessions.md
        ├── tasks/{current,backlog}.md
        ├── plans/decisions.md
        ├── flaws/{README,log}.md
        ├── inefficiencies/log.md
        ├── reviews/README.md
        ├── workflows/active.md
        ├── system/{ai-models,environments}.md
        ├── user/{identity,preferences}.md
        ├── overrides/rules.md
        └── secrets/{README.md,.gitignore}
```

Every core file's sha256 is recorded in `MANIFEST.sha256` (line-prefixed
with the hash, then the relative path). `context-sync verify` runs
`sha256sum --check --status MANIFEST.sha256` from inside `core/`; a
non-zero exit triggers the rollback path.

### 5.2 The two editions (`rules/`)

The two editions differ by **platform**, not by mission:

- **Cloud/sandbox edition** (`ai-engineering-protocol.md`): the agent
  starts in an empty workspace, must clone the project repo, must use a
  PAT for any push, and must follow the PAT strip-and-readd dance around
  every push.
- **Local edition** (`ai-engineering-protocol-local.md`): the agent is
  already inside the repo on the developer's machine, uses the user's
  existing git credentials (no PAT, no clone), and pushes directly.

Everything else — the 19 steps, the six phases, the quality gates, the
common pitfalls, the `.context/` rules — is identical between the two.
This is deliberate: keeping the platform-specific surface small means
the spec lives in exactly one place per platform, and a role overlay
(~80 lines) can re-scope either edition without forking it.

Both editions open with the **Zero-Interruption Principle**: once the
agent starts, it runs to completion without asking the user questions.
Missing inputs use documented defaults; only an unresolved blocker
(missing PAT for a private repo, build broken beyond the agent's
ability to fix) stops early.

### 5.3 The Ten Binding Rules

Both editions list the same ten rules at the top — the ones whose
violation costs the most when an agent's recall erodes late in a long
session:

1. Read `.context/` before touching anything; update it before ending.
2. Two zones: `core/` is read-only (never write one byte); `memory/` is
   writable.
3. Two surfaces, never one commit: project code and `.context/` are
   staged and committed separately.
4. Append-only logs only grow. Before committing one, its `git diff`
   must show no removed lines.
5. No secret values in any tracked file — including inside recorded
   commands.
6. Commit each logical change, push after each commit, ask permission
   for neither.
7. A missing credential is a missing input — ask for it up front, not
   after the failure. (Cloud edition; local edition rephrases to "a
   missing input only the user can supply.")
8. Never guess your model version or today's date — system prompt /
   `date -u +%F`, or record `unknown`.
9. Phase 1 runs for every session, however small the task.
10. Re-read the Exit checklist right before finishing.

### 5.4 The Common Pitfalls (43 in the cloud edition)

Both editions accumulate hard-won lessons in a "Common Pitfalls (Learned
the Hard Way)" section. The cloud edition has 43; the local edition has
the same 43 with minor wording adjustments. Highlights:

- **#25** — Don't guess your own model version. System prompts often
  don't state it; guesses propagate across sessions as wrong data.
- **#28** — Don't treat any task as "too small for Phase 1." Skipping
  Phase 1 is the most common protocol violation.
- **#30** — Don't ask permission for the default next step. The
  Zero-Interruption Principle covers "permission" as well as
  "clarification."
- **#33** — Don't update the protocol by hand, and never re-bootstrap
  over an existing `.context/`.
- **#34** — A missing credential is a missing input, not a permission
  question. Cloud agents need a PAT for every push; don't wait for a
  404 to discover that.
- **#37** — Don't backlog a fix you could make with the same keystrokes
  it took to write the backlog entry.
- **#38** — Don't `git add -A` (or `git add .`) when both surfaces are
  dirty. Stage per surface.
- **#39** — Don't commit an append-only file whose diff shows removed
  lines.
- **#40** — Don't record a command containing a credential. The
  authenticated clone/push one-liners must never land in
  `system/environments.md`.
- **#41** — Don't write dates from memory. Run `date -u +%F`.
- **#42** — Don't claim verification without the evidence. "Tests pass"
  must carry the exact command and its observed result.
- **#43** — Don't absorb another agent type's identity from the
  project's memory. Your edition comes from YOUR agent type at session
  start.

### 5.5 Role overlays (`roles/`)

A role overlay is a small file (~50–90 lines) that re-scopes a base
edition. The agent is handed **two files**: the base edition matching
its platform plus one role file. Where the role file and the base
edition conflict, **the role file wins**. Everything the role file
doesn't mention stays exactly as the base edition says.

| Role | File | Mission | Writes code? | Report filename |
|---|---|---|---|---|
| Engineer (default) | *(none — base edition as-is)* | discovery + review + fix all safe issues | yes | `YYYY-MM-DD-review.md` |
| Feature engineer | `feature-engineer.md` | design + build a requested feature | yes | `YYYY-MM-DD-feature-review.md` |
| Reviewer | `reviewer.md` | audit and report; change nothing | no | `YYYY-MM-DD-review.md` (plain) |
| Security auditor | `security-auditor.md` | security-only deep audit | security fixes only | `YYYY-MM-DD-security-review.md` |
| Docs agent | `docs-agent.md` | make the docs match the code | docs only | `YYYY-MM-DD-docs-review.md` |

A role file may override session parameters, review checklists, and
execution steps (skipping or no-op'ing steps that don't apply). It may
**never** override the `.context/` rules (append-only, no secrets,
entry templates, `chore(context):` prefix), Phase 5 (Steps 15–17 — the
memory update is mandatory for every role, every session, including
sessions with no findings), quality gates, or the base edition's
git/push workflow.

The reviewer role is the lightest: Steps 1–9 run as written (it still
installs dependencies and runs baseline health — a review without a
baseline is a guess), Phase 3 is skipped entirely (no fixes, no code
commits), Step 14 (changelog) is a no-op, and every Critical/High
finding becomes a `tasks/backlog.md` entry written so a fresh engineer
session can act without this session's chat history.

The feature-engineer role is the heaviest overlay: Phase 2 becomes
DESIGN (enumerate decisions, record each nontrivial one as an ADR), and
Phase 3 becomes IMPLEMENT (build in reviewable increments, every quality
gate binds, verify the feature end-to-end before calling it done). It
explicitly forbids "no skipping design because the feature 'is simple'"
— the one-ADR minimum stands.

### 5.6 The schema (`schemas/`)

`context-schema.md` is the **single source of truth** on every file in
`.context/`: where it lives, who owns it, how it may be written, and
which scope its facts belong to. When any other document (a README, an
edition, a template comment) disagrees with this schema, **this schema
wins** — and the disagreement is a flaw to log.

The JSON mirror (`context.schema.json`) is generated by hand and must
be updated in the same commit as any schema change. Consumers:
`context-sync`, future check tooling, agents that prefer structured
data. The JSON currently records `coreVersion: 0.2.0` (a known lag —
the actual `core/VERSION` is 0.3.0; this is a documentation drift, not
a functional defect, since `context-sync` reads `VERSION` not the JSON
`coreVersion` field).

The schema defines:

- **Two zones** with their ownership and sync models.
- **Five write modes:** append-only, overwrite, update-in-place,
  generated, local-only.
- **Five fact scopes:** project, agent-type, machine, agent-model, user.
- **The binding rules:** edition selection is a function of the agent's
  type at session start (never read from memory); machine blocks apply
  only where the "Identify by" matches; credential flows are
  agent-type facts; corrections to append-only logs are appended, never
  edited in; secret values live only in `memory/secrets/`; `core/` is
  read-only.
- **Commit prefixes:** `chore(context):` for memory, `docs(review):`
  for reviews, `chore(context): update core to <version>` for core
  updates.

### 5.7 The templates (`templates/`)

The templates are the **source of truth for generated files**. At
bootstrap, `core/templates/memory/` is copied verbatim into
`.context/memory/`, `core/templates/context-README.md` becomes
`.context/README.md`, `core/templates/kickoff.md` becomes
`.context/kickoff.md`, and `core/templates/AGENTS.md` becomes the root
`AGENTS.md` (only if it doesn't already exist).

Each memory template carries an HTML comment at the top with the entry
format for that file — agents read the template before writing and never
invent formats. If a file's in-repo template comment and the schema's
mode column disagree, the schema wins.

On `context-sync update`, only `.context/README.md` is refreshed from
its template (the `cmd_update` function explicitly does
`cp "$CORE_DIR/templates/context-README.md" "$CONTEXT_DIR/README.md"`).
The root `AGENTS.md` and `.context/kickoff.md` are **not** touched by
update — they are project-owned data, and changes to their templates
require a session to regenerate them deliberately (the kickoff template's
HTML comment spells out the regeneration rules).

### 5.8 The CHANGELOG (versioning)

`core/CHANGELOG.md` records one entry per released core version, newest
first. Semver: breaking changes to the `.context/` spec or memory
layout bump MAJOR; new features (roles, pitfalls, templates, schema
fields) bump MINOR; wording and fixes bump PATCH.

Three releases so far:

- **0.1.0 (2026-07-13, retroactive):** the sibling-clone era. Two
  protocol editions at the package root, `context-skeleton/`
  bootstrapped into projects as a flat `.context/`, structural-vs-data
  sync per `SYNC.md`, package cloned beside every project as
  `../context`.
- **0.2.0 (2026-07-14, "the vendored-core release"):** the protocol no
  longer lives in a sibling clone — it travels inside every project as
  `.context/core/`. Two-zone layout (`core/` read-only +
  `memory/` writable). `memory/overrides/rules.md` and
  `memory/core.lock` introduced. Unified schema. `context-sync` POSIX
  tool. Weak-agent translation layer (root `AGENTS.md`).
- **0.3.0 (2026-07-21, "the harvest release"):** closes the upstream
  loop. `context-sync harvest` collects open flaws, `Upstream: candidate`
  inefficiencies, and `[core-defect]` overrides from every fleet-listed
  project into `inbox/harvest-<date>.md`. `fleet.md` registry.
  Schema fields for harvest opt-in. Migration from 0.2.x: none required
  (additive and opt-in).

---

## 6. Deep Dive — the `memory/` Module (Zone 2, writable)

`memory/` is **this project's living memory**. It is owned by the
project, written by every session per each file's mode, and never
touched by `context-sync` (except the single file `memory/core.lock`,
which only `context-sync` writes). The full spec is `core/schemas/
context-schema.md`; every writable file also carries its entry template
in an HTML comment at the top.

### 6.1 File inventory, write modes, and scopes

| Path (under `.context/memory/`) | Mode | Scope | Holds |
|---|---|---|---|
| `agents/sessions.md` | append-only | project | One entry per session: agent, model, platform, task, commits, outcome |
| `tasks/current.md` | overwrite | project | The one task in progress — doubles as the concurrency lock |
| `tasks/backlog.md` | append-only | project | Open items for future sessions |
| `plans/decisions.md` | append-only | project | ADR-style decisions — respected, not relitigated |
| `flaws/log.md` | append-only | project→package | Friction with the `.context/` system itself; flows upstream via `harvest` |
| `flaws/README.md` | generated | project | The flaws-vs-inefficiencies split rule |
| `inefficiencies/log.md` | append-only | project | Friction with the project's code, env, deps. Opt-in `Upstream: candidate` line for protocol-level friction |
| `reviews/YYYY-MM-DD-*.md` | new file per session | project | Session reports (commit as `docs(review):`) |
| `reviews/README.md` | generated | project | Naming + report structure |
| `workflows/active.md` | overwrite | project | Standing session parameters + protocol recorded "by agent type" (both editions, never one) |
| `system/environments.md` | update-in-place | **machine** | One block per machine/sandbox, keyed by an "Identify by" line |
| `system/ai-models.md` | update-in-place | **agent-model** | Registry + observations per agent/model |
| `user/identity.md` | update-in-place | user | Who the user is |
| `user/preferences.md` | update-in-place | user | Standing preferences, each bullet with provenance |
| `overrides/rules.md` | update-in-place | project | Project-local protocol adjustments (beat the edition, except secrets/append-only) |
| `core.lock` | overwrite (by `context-sync`) | project | Last-known-good core version + when verified |
| `secrets/<slug>` | local-only | machine | One secret per file; line 1 = value. Self-gitignored |
| `secrets/README.md`, `secrets/.gitignore` | generated | project | The secrets hard rules; the self-ignore |

### 6.2 The five write modes

- **append-only** — entries are only added at the bottom; corrections
  are appended, never edited in. Sole exception: byte-identical
  duplicate entries may be removed, leaving a one-line note in place.
  Applies to: `sessions.md`, `tasks/backlog.md`, `plans/decisions.md`,
  `flaws/log.md`, `inefficiencies/log.md`.
- **overwrite** — current-state only; replace the content, history
  lives in the append-only logs. Applies to: `tasks/current.md`,
  `workflows/active.md`, `core.lock` (the last by `context-sync`
  only).
- **update-in-place** — structured records updated where they stand (a
  row, a block, a bullet); never wholesale replaced. Applies to:
  `system/environments.md`, `system/ai-models.md`, `user/identity.md`,
  `user/preferences.md`, `overrides/rules.md`.
- **generated** — created from a `core/templates/` file at bootstrap,
  then maintained as data. Applies to: `flaws/README.md`,
  `reviews/README.md`, `secrets/README.md`, `secrets/.gitignore`, and
  the root `.context/README.md`.
- **local-only** — never tracked by git, never travels. Applies to:
  every file under `secrets/` except `README.md` and `.gitignore`.

### 6.3 The five fact scopes (the contamination rules)

`.context/` memory serves **every** agent that will ever work on the
project: local and cloud, strong and weak, on any machine. The single
biggest failure mode observed in the field is **scope contamination** —
one agent records a fact true only for its own type, machine, or model,
and the next agent of a different kind reads it as binding.

Every fact belongs to exactly one scope. Record it so the scope is
explicit:

| Scope | Definition | Where it lives | How it's keyed |
|---|---|---|---|
| **project** | True for this repo regardless of who works on it (repo URL, default branch, decisions, backlog) | most of `memory/` | nothing — unqualified facts are project facts |
| **agent-type** | True only for local OR only for cloud/sandbox (edition, credential flow, clone steps) | **never as a single value** — always keyed "by agent type", naming both branches | explicit `local: … / cloud: …` |
| **machine** | True only on one machine/sandbox (paths, installed tools, verified commands) | `system/environments.md` blocks | the block's "Identify by" line |
| **agent/model** | True only for one agent or model (capabilities, blind spots) | `system/ai-models.md` | the registry row |
| **user** | About the person (identity, preferences) | `user/` | provenance markers |

**Binding consequences:**

1. Edition choice is a function of your agent type at session start —
   never of memory. `workflows/active.md` records the protocol "by
   agent type", naming BOTH editions. If you ever find a single edition
   recorded there, that's the previous agent's type leaking; follow
   your own type and fix the record.
2. A machine-scoped block applies only where its "Identify by" matches.
   Never run another environment's verified commands as if they were
   yours.
3. Credential flows are agent-type facts. PAT steps exist only in the
   cloud edition; a local agent that finds PAT instructions in memory
   ignores them and logs a flaw.
4. When writing, ask: "would this sentence be wrong for an agent of the
   other type, on another machine?" If yes, key it to its scope or
   don't write it.

The canonical failure (Pitfall #43): a cloud agent bootstraps a repo,
the user pulls it locally, and the local agent starts doing PAT dances
and re-cloning because it read the cloud agent's records as its own
instructions. The fix is the explicit "by agent type" keying in
`workflows/active.md` and the "Identify by" line on every
`environments.md` block.

### 6.4 Overrides — project-local protocol adjustments

`memory/overrides/rules.md` is the **one sanctioned place** a project
bends the protocol without forking core. Sessions read it right after
loading their edition; where an override and the edition conflict,
**the override wins** — with two exceptions that nothing can override:
secret-handling rules and the append-only guarantee.

Overrides are for standing, project-shaped deltas ("this repo squashes
to a release branch, not main", "reports go in docs/reports/ for legacy
reasons"). They are **not** a scratchpad for session instructions
(those die with the session) or user preferences (those go in
`user/preferences.md`).

Because overrides survive core bumps, an override can quietly keep a
project diverged from a core that was later fixed. So every override is
tagged by kind:

- **`[core-defect]`** — core is wrong/broken here and this bullet is a
  local patch. `context-sync harvest` collects these into the package
  so the fix ships in a future core and the next project bootstrapped
  from it never rediscovers the workaround.
- **`[project-local]`** — core is fine; this project just works
  differently (git-flow, house style). Never harvested; stays local.

This repo's `overrides/rules.md` currently has `*(none yet)*` — no
project-local deltas.

### 6.5 Secrets — the local-only zone

`memory/secrets/` is the only directory whose contents never travel
with the repo. Its `.gitignore` is self-ignoring:

```
*
!.gitignore
!README.md
```

Everything in the directory is ignored except the `.gitignore` itself
and the `README.md` that documents the rules. Six hard rules
(`secrets/README.md`):

1. Never commit a value. The `.gitignore` enforces it — never weaken
   it, never `git add -f` anything in this directory. Before writing a
   new secret file, prove it's ignored: `git check-ignore
   .context/memory/secrets/<file>` must succeed.
2. Never echo a value — not in chat, logs, reports, commit messages, or
   error output.
3. Never copy a value into a tracked file. Refer to secrets by filename
   (`secrets/github-pat`), never by value.
4. `chmod 600` every secret file you create.
5. This directory does not travel. A fresh clone has an empty
   `secrets/`. If a secret you need is missing, ask the user.
6. The user owns the credentials. Agents never create, rotate, or
   revoke credentials on their own.

Format: one secret per file. The filename is the slug (`github-pat`,
`openai-api-key`, `staging-db-password`). **Line 1 is the value,
alone.** Lines 2+ are notes (scope, date added, rotation policy).
Read line 1 into an env var; never inline a value into a command
(inlined values end up in shell history and process listings):

```bash
export GIT_TOKEN="$(head -n1 .context/memory/secrets/github-pat)"
```

Trade-off to know: values here are plaintext at rest, like a `.env`
file — protected by file permissions and the gitignore, not
encryption. Prefer narrow-scope, expiring credentials (fine-grained
PATs scoped to one repo beat classic full-account tokens).

### 6.6 Reading order at session start

The schema prescribes a strict reading order so every agent starts
from the same orientation:

`.context/README.md` (zone map) → `kickoff.md` (front door, points
into memory) → `memory/workflows/active.md` (standing parameters) →
`memory/agents/sessions.md` (last 3–5 entries — who worked here before,
with which model, and what they did) → `memory/tasks/current.md` (is a
task marked in-progress?) → `memory/tasks/backlog.md` (open items
waiting for a session like this one) → `memory/inefficiencies/log.md`
(known project traps) → `memory/flaws/log.md` (known protocol traps —
don't re-hit a logged flaw) → `memory/plans/decisions.md` (decisions
already made — don't relitigate) → `memory/overrides/rules.md` (project
adjustments) → `memory/system/` (machines + agent/model registry) →
`memory/user/` (identity + preferences) → note what's in `memory/secrets/`
(never print values).

The order matters: `current.md` before `backlog.md` (don't start if
another session is live), `inefficiencies/log.md` before
`flaws/log.md` (project traps before protocol traps), `decisions.md`
before any fix (don't "fix" code into violating a prior decision).

### 6.7 The translation layer — how weaker agents consume this system

Not every agent reads a 986-line edition reliably. The system degrades
gracefully through **three tiers**, all generated from core — never
hand-maintained per project:

1. **`AGENTS.md` at the project root** (~60 lines, from
   `core/templates/AGENTS.md`): the zones, the read-only rule for
   `core/`, the entry point (`.context/kickoff.md`), and the condensed
   binding rules. Optionally also copied as `CLAUDE.md` and
   `.github/copilot-instructions.md` for tools that auto-load those
   paths. **This is the floor** — an agent that reads nothing else
   still learns where memory lives, what it must never write to, and
   where to start.
2. **`.context/kickoff.md`** — the front door: typed entry steps that
   route by agent type and point into core. Filled with project facts
   at bootstrap, kept current by sessions.
3. **The full edition in `core/rules/`** — the complete instruction
   set for agents that can hold it.

Each tier links down to the next; no tier contradicts another because
all three are rendered from the same core version. A weak agent
following only tier 1 does less, but nothing **wrong** — it cannot
clobber `core/` (rule stated in tier 1), cannot miss the entry point,
and cannot pick the wrong edition (the kickoff routes by type).

---

## 7. How Core and Memory Connect (the E2E picture)

The two zones are designed to interlock without ever leaking into each
other. The connection points are:

1. **Bootstrap** writes `core/` (read-only thereafter) and seeds
   `memory/` from `core/templates/memory/`. After bootstrap, `core/`
   never changes except via `context-sync update` (whole-tree, memory
   untouched).
2. **`memory/core.lock`** is the **only file `context-sync` writes
   inside `memory/`** — and only `context-sync` writes it. It records
   the last-known-good core version so `rollback` knows what to
   restore.
3. **`memory/workflows/active.md`** records the protocol edition "by
   agent type" (naming both branches) — it points into `core/rules/`
   without duplicating the protocol text.
4. **`memory/overrides/rules.md`** bends the protocol without forking
   `core/` — overrides win over the edition except on secrets and
   append-only.
5. **`memory/flaws/log.md`** is the **upstream back-channel**: protocol
   friction recorded here flows to the package via `context-sync
   harvest` and comes back as a core fix on the next `context-sync
   update`.
6. **`memory/inefficiencies/log.md`** does the same for protocol-level
   project friction, but only when an entry is explicitly marked
   `Upstream: candidate`. Unmarked entries are project-local and never
   harvested.
7. **`memory/tasks/current.md`** is the **concurrency lock**: if it
   shows a live session, don't start. One agent per repo at a time.

The whole system is a **closed loop with five sub-flows**: bootstrap
(one-time) → session entry → protocol execution → memory update → sync/
harvest (back to package → next core release → next bootstrap/update).
Nothing in the loop requires the project to know about the package
after bootstrap, and nothing in the package requires write access to
any project — `harvest` is read-only on the projects.

---

## 8. Findings (by severity)

### Critical
None.

### High
None.

### Medium

**M1 — `context.schema.json` `coreVersion` field is stale.**
- **Description:** `core/schemas/context.schema.json` line 5 records
  `"coreVersion": "0.2.0"`, but `core/VERSION` is `0.3.0`. The JSON is
  documented as a machine-readable mirror of `context-schema.md` and
  must be updated in the same commit as any schema change.
- **Impact:** Any consumer that reads `coreVersion` from the JSON (the
  schema's `$comment` lists "context-sync, future check tooling, agents
  that prefer structured data") would see the wrong version. In
  practice, `context-sync` reads `core/VERSION` (not the JSON), so the
  drift is documentation-only — but it's exactly the kind of latent
  inconsistency that bites when a future tool trusts the JSON.
- **Recommendation:** This is a **core-zone defect** — the fix belongs
  in the protocol package, not in this project. Log it as a
  `[core-defect]` override in `memory/overrides/rules.md` so the next
  `context-sync harvest` picks it up. Do **not** patch
  `.context/core/schemas/context.schema.json` in place (Binding Rule
  #2: never write under `core/`).
- **Status:** flagged for upstream — recorded as override
  `[core-defect]` schema-coreversion-drift (see
  `memory/overrides/rules.md`).

### Low

**L1 — `flaws/log.md` and `inefficiencies/log.md` are still empty.**
- **Description:** Session 1 (bootstrap) left both logs empty. That is
  valid for a bootstrap session, but it means no protocol-level traps
  are recorded yet. Future agents have nothing to warn them.
- **Impact:** Minor — the logs grow naturally as sessions accumulate.
  No action required; just noted for completeness.

**L2 — `system/environments.md` has only one block (the bootstrap
macOS machine).**
- **Description:** Cloud/sandbox environments haven't been recorded
  yet. This session adds the second block (Z sandbox).
- **Impact:** Minor — the registry grows as new environments run
  sessions. No action beyond updating the file in Step 16.

**L3 — `system/ai-models.md` has only one row (Claude Code /
claude-opus-4-8).**
- **Description:** Same pattern as L2. This session adds the Super Z /
  GLM row with `model: unknown` (Pitfall #25 — never guess).
- **Impact:** Minor.

### Nice to Have

**N1 — Root `AGENTS.md` is accurate but minimal.**
- **Description:** The current root `AGENTS.md` is a faithful copy of
  `core/templates/AGENTS.md` with `<PROJECT_NAME>` filled in as "Glyph".
  It captures the 10 binding rules but does not surface the `core/` and
  `memory/` module structure for fast agent orientation.
- **Impact:** Tier-1 agents (the weak-agent floor) must read
  `.context/README.md` and `.context/kickoff.md` to learn the module
  layout — a small but real friction for the most common entry path.
- **Recommendation:** Add a compact "Core + Memory at a glance" section
  to the root `AGENTS.md` (the file is project-owned after bootstrap and
  is **not** overwritten by `context-sync update` — only
  `.context/README.md` is refreshed on update). Keep it under ~30 lines
  so the file stays tier-1-friendly. Note the addition in the file's
  HTML comment so a future bootstrap-from-template knows it was a
  deliberate enhancement.
- **Status:** implemented in this session — see the new section in
  `AGENTS.md`.

---

## 9. Fixes Applied

- **`AGENTS.md` (root):** added a compact "Core + Memory at a glance"
  section (~30 lines) that surfaces the two-zone layout, the
  `context-sync` commands, the memory file inventory with write modes,
  the five fact scopes, and the three-tier translation layer. The
  existing 10 binding rules and the schema pointer are preserved
  unchanged. The HTML comment is updated to note the addition.

  Commit prefix: `docs:` — the root `AGENTS.md` is project-owned
  documentation (it lives at the project root, not under `.context/`),
  generated from `core/templates/AGENTS.md` at bootstrap but not
  auto-refreshed by `context-sync update` (only `.context/README.md` is).
  Editing it does not violate Binding Rule #2 (never write under
  `core/`) — `core/` and the root `AGENTS.md` are different paths.
  Session 1 used `docs:` for project-level doc changes, so this follows
  the established convention.

- **`memory/overrides/rules.md`:** added the first override bullet,
  tagged `[core-defect]`, recording the `context.schema.json`
  `coreVersion` drift so the next `context-sync harvest` picks it up
  for an upstream fix.

- **`memory/tasks/current.md`:** set to this session's task at start;
  cleared (set to idle) at end per Step 15.

- **`memory/agents/sessions.md`:** appended Session 2's entry per the
  template (date, agent, model, platform, role, core version, task,
  commits, outcome, open items, report path).

- **`memory/system/ai-models.md`:** added the Super Z / GLM row
  (`model: unknown` per Pitfall #25 — system prompt does not state the
  exact model ID).

- **`memory/system/environments.md`:** added a second block for the
  Z sandbox (Linux, `/home/z/my-project/glyph` workspace).

- **`memory/inefficiencies/log.md`:** appended this session's friction
  (the `context.schema.json` drift discovery, the absence of a sibling
  package clone preventing `context-sync status` from finding an update
  source).

- **`memory/tasks/backlog.md`:** no new items — the four existing
  backlog items (MVP, Phase-0 proof, repo/service split, README layout)
  remain the right next steps; this session was a research pass, not a
  build session.

---

## 10. Open Items

- The four backlog items from Session 1 stand unchanged (MVP stages
  1–4 + drift monitor; Phase-0 proof; repo/service split decision;
  README package layout). None were addressed by this session — this
  was a research pass on the `.context/` protocol itself, not on
  Glyph's product scope.
- The `context.schema.json` `coreVersion` drift (M1) is recorded as a
  `[core-defect]` override and will flow upstream on the next
  `context-sync harvest`. No local fix is possible (Binding Rule #2).

---

## 11. Recommended Next Steps

1. **Greenlight the Phase-0 proof** (RESEARCH.md §9): pick any target
   with obvious opaque codes and a visible UI, build stages 1–4
   minimally, verify Rosetta auto-derives the code dictionary. This is
   the gate for building the rest of Glyph.
2. **Decide the repo/service split** (RESEARCH.md §11): one repo with
   stages as packages vs. capture-tool + catalog-service. Decide
   before the MVP build starts so the catalog store (SQLite local →
   shared DB later) is chosen with the right shape.
3. **Add a sibling package clone** (optional): if you want
   `context-sync status` to find update sources automatically from
   this sandbox, clone `https://github.com/TisoneK/.context.git` as a
   sibling and set `CONTEXT_PKG` to its path. Not required — sync
   never fails a session — but useful for staying current on core.
4. **Rotate the PAT** used for this session. The token was pasted in
   chat, used as a transient env var, stripped from `.git/config`
   after every push, and unset at session end (Step 19) — but rotate
   it anyway per the protocol's secret-handling rules.

---

## 12. Verification

- **Core integrity:** `sh .context/core/bin/context-sync verify` →
  `core OK: every file matches MANIFEST.sha256 (0.3.0)` — verified
  2026-07-30.
- **Core drift:** `sh .context/core/bin/context-sync status` → core
  0.3.0, locked 0.3.0, no source reachable — verified 2026-07-30.
- **Date:** `date -u +%F` → 2026-07-30 — used for all session entries,
  the report filename, and the `verified` field.
- **Append-only diffs:** before committing `agents/sessions.md`,
  `tasks/backlog.md`, `inefficiencies/log.md`, and `flaws/log.md`,
  `git diff <file>` was reviewed to confirm every changed line is `+`
  (Pitfall #39).
- **No secrets in diff:** `git diff` scanned for `x-access-token`,
  `github_pat_`, `ghp_`, `gho_` — all empty (Pitfall #40).
- **Two-surfaces rule:** this session touched only the `.context/`
  surface (memory updates + root `AGENTS.md`). No product code was
  modified (there is no product code yet). All commits use
  `chore(context):` or `docs(review):`.
