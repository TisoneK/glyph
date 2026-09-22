# Agent Instructions — Glyph

<!-- Generated at bootstrap from .context_ledger/core/templates/AGENTS.md.
Refreshed on core updates (fill Glyph again). THE WEAK-AGENT
FLOOR — this is the one file some sessions on this repo will ever read in
full, so the handful of behaviors whose silent skip causes real, hard-to
-undo damage (check in before reading/analyzing; close a full office at
the door; never leak a secret; never mix commit surfaces; never stop
without pushing) are stated here directly, not only routed to
kickoff.md. Everything else — full reading order, gates, roster/collab
mechanics, review checklists — IS routed to kickoff.md's phases and the
vendored core, not restated here (core 2.0.0 cut that three-way
duplication down to router-only; core 2.0.2 restored the check-in line
after cutting it caused a real collision; core 2.0.3 restored the rest
of this list on the same reasoning instead of waiting for each to cause
its own incident — see CHANGELOG). Bootstrap also installs a CLAUDE.md
pointer so Claude Code (which auto-loads CLAUDE.md, not this file)
reaches this same front door. If the project uses other agent tools, add
a one-line "read AGENTS.md first" pointer to their entrypoint too —
Copilot: .github/copilot-instructions.md, Cursor: .cursor/rules, Gemini:
GEMINI.md, Codex/others: this AGENTS.md. -->

This repo uses the `.context_ledger/` protocol: persistent agent memory
plus a vendored copy of the full workflow, committed to git.

**Do this before reading anything else in this repo — including the
rest of this file:** add your row to
[`memory/office/agents/roster.md`](.context_ledger/memory/office/agents/roster.md)
(a real name you pick — never your own model or product name; plus a
codename `S<NNN>`, your model, one line on what you're doing, and
Status `Working`), then commit and push it:
`chore(ledger): <name> (<codename>) checks in — <task>`. Reading or
analyzing first — even skimming this file to the end before pushing —
is how two sessions collide mid-task without ever seeing each other on
the board; the check-in **is** the session's first write, not a
formality to get to once you're settled in.

**Before that check-in push, look at the last entries in
[`memory/office/agents/sessions.md`](.context_ledger/memory/office/agents/sessions.md):
if the count already exceeds `office_size` (default 20), the office is
full.** Close it as part of checking in, before any other read —
`sh .context_ledger/core/bin/ledger-history close` (dry run, then
`--confirm`) — and only then sign the fresh board it opens. This is not
optional tidiness: an office read past the door trigger is exactly how a
session gets misdirected by stale session numbers and a stale roster.

**Then** read [`.context_ledger/kickoff.md`](.context_ledger/kickoff.md)
and follow it, in order. Its Phase 2 covers this same check-in (and the
office-close trigger) with the full mechanics if anything above was
unclear, then routes you — local or cloud/sandbox agent, task scaled to
size — to the right instruction set.

Three more rules that can't wait either:

- **Never write under `.context_ledger/core/`** — it is a read-only,
  versioned copy of the protocol, replaced only as a whole tree by
  `ledger-sync`.
- **No secret values in any tracked file, ever** — not in `.context_ledger/`,
  not in project code, not inside a recorded command. Values live only in
  `.context_ledger/memory/secrets/` (self-gitignored).
- **Project code and `.context_ledger/` memory are staged and committed
  separately** — `git add .context_ledger/` for memory, explicit paths
  for project code. Never `git add -A` (or `git add .`) while both are
  dirty; that's how the two surfaces end up mixed in one commit.

And one to close on: **the session is not done until every change is
committed AND pushed.** If the user has to remind you to push, that is a
logged protocol failure, not a minor slip.

Reading order past check-in, gates, roster/collaboration mechanics, and
review checklists are `kickoff.md`'s job to route you to. Full spec if
something here and there ever disagrees:
`.context_ledger/core/schemas/ledger-schema.md`.

---

## Project-owned notes (not generated — keep when regenerating this file)

**What this repo is:** `glyph` — a Python reverse-engineering toolkit for
authorized targets: capture (HAR / live browser) → catalog → schema, rosetta,
sensitive, SNI, VPN-config, mobile and codegen stages, with a Textual TUI over
a shared SQLite catalog. Product docs live in `README.md`, `RESEARCH.md` and
`RESEARCH-DEEP-DIVE.md`.

**The catalog is multi-target (ADR-12).** A `targets` table holds every host
ever captured, and every data row (flows, endpoints, fields, dictionary,
page_observations, findings, vpn_configs) carries a `target_id`. Capturing
`betika.com` and then `sportybet.com` leaves BOTH in the catalog, each
queryable via `glyph target show <host>` and filterable via `--target`.

Key invariants a future agent must respect:

- **`set_target(host)` activates; `clear_target()` wipes only that target's
  rows.** A run calls both — it does NOT call `reset()` (a full wipe, reserved
  for tests and a future `--reset` flag).
- **Every write stamps a NON-NULL `target_id`** (explicit > active > the
  reserved "(unassigned)" bucket, id=0). This is required: SQLite treats
  `NULL != NULL` in UNIQUE constraints, so a nullable `target_id` would break
  upsert dedup.
- **Reads filter to the active target by default**, falling back to "all
  targets" when no target is active. Pass `all_targets=True` to force all, or
  an explicit `target_id` for a specific one.
- **`capture` accumulates; `run` clears.** `glyph capture har/live` adds
  traffic to the active (or unassigned) target; `glyph run har/live` activates
  and clears one target first (fresh analysis).
- The "(unassigned)" target (id=0) is where rows land when no target is set
  (legacy tests, REPL scratch). It is visible in `glyph target list` and
  clearable with `glyph target rm 0`.

Full design and migration notes: `ADRs 12/14/16` in
`.context_ledger/memory/office/plans/decisions.md`, and the frozen office's
`2026-07-31-multi-target-schema.md` review.
