# User Preferences (update in place)

How the user likes things done **on this project**. Seeded from
Pre-Flight at bootstrap; grows as sessions reveal preferences.

## Workflow
- Follow the `.context/` protocol: ADRs + docs alongside implementation; commit and push each logical change. (pre-flight)
- New systems start research-first — shape scope, features, and boundaries as a doc before building. (approved pattern, 2026-07-29)

## Communication
- Chat summaries in plain language; keep the technical depth in the docs/reports. (stated, 2026-07-29)
- **Don't make the user ask for commit/push/.context updates.** After each logical
  change, commit + push + update `.context` automatically as one flow — this is the
  protocol default (Binding Rule 6 / Pitfall #30), and having to remind me is itself
  friction. Surface it briefly, don't wait to be told. (feedback, 2026-07-31)

## Code style
- Prefer modular packages over one long file — split code into focused
  modules/subpackages; a single long file is "unmaintainable." (stated,
  2026-07-30) Applied: `glyph/` is one subpackage per pipeline stage.

## Runtime & tooling
- **Target Python 3.13.** The user prefers 3.13 specifically because it is
  stable on Windows and avoids platform issues (Pydantic works well on 3.12
  and 3.13; 3.13 is the pick). (stated, 2026-07-30)
  - **Note / open action:** the base package was built targeting 3.9 (the
    only interpreter installed on bao@local) using stdlib dataclasses. This
    conflicts with the 3.13 + Pydantic preference — retarget decision pending
    with the user (see `agents/sessions.md` Session 4 follow-up).
- **Pydantic is the preferred model/validation layer** (works well on 3.12/
  3.13). Reconsider ADR-2's "zero required dependencies" base if adopting it —
  Pydantic is a hard dependency. (stated, 2026-07-30)

## Testing
- **Real-world testing over green unit tests.** Tests can pass 100% because
  they were "conditioned to pass that way" while the software still fails in
  the real world. The user prefers validation against real targets/inputs, not
  just synthetic fixtures. (stated, 2026-07-30)
  - **Why:** unit tests over hand-authored inputs prove internal consistency,
    not that the tool works against a messy real target.
  - **How to apply:** for any stage, pair unit tests with an integration/real-
    world run (a real captured HAR from an authorized target, a live capture,
    an end-to-end pipeline run) before calling it "done." Never report "N tests
    pass" as evidence the software works in the real world — say explicitly
    what the tests do and don't cover.

## Review depth
- **When you find an issue, fix it AND hunt for the same pattern elsewhere —
  don't go round and round.** A single bug is rarely unique; the same shape
  likely exists in sibling code. Finding one → fix that one → grep for the
  pattern → fix all of them in the same pass. Reporting "fixed the one you
  pointed at" while leaving the identical bug two files over is a
  half-fix that forces the user to point at the next instance. (feedback,
  2026-07-31, after the `glyph snihunt <target>` UX gap — the same
  "command only operates on a pre-existing catalog, not a direct target"
  shape was likely present in other commands too.)

## UX
- **Long-running commands MUST show live progress.** A command that makes
  N network calls (DNS, CT logs, reverse-IP) with no output looks frozen —
  the user can't tell if it's working or hung. Print a progress line per
  phase / per item so the terminal shows activity. This is especially true
  on Windows PowerShell where there's no spinner by default. (feedback,
  2026-07-31, after `glyph snihunt betika.com` hung silently for a minute.)

## Risk & approvals
- Naming and scope are the user's call — judge a name on its own merit; do NOT couple a standalone tool to sibling projects. (correction, 2026-07-29)
