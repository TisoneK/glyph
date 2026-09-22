# Flaws Log (append-only — flows to the protocol package)

Friction caused by the `.context_ledger/` system or the protocol itself. See
`README.md` in this directory for the split between `flaws/` and
`inefficiencies/`.

Append-only, but compactable — the log never grows without bound:

- **Resolved entries move verbatim** to cold storage: once an entry is
  explicitly marked `RESOLVED` / `superseded` / fixed, cut it unchanged
  into `archive.md` in this directory so startup reads only the live
  entries. Age alone never makes an entry eligible — an unresolved flaw
  stays here as a live trap.
- **Repeats roll up:** when 3+ entries describe the same recurring
  protocol trap, append ONE consolidated `Recurring` entry — the pattern,
  how many times, the current workaround — and move the individual
  entries verbatim into `archive.md`. The live log keeps the pattern, not
  the repeats.

`ledger-mem prune` reports log sizes, archive-eligible entries (`--list`
names them), and roll-up candidates.

<!-- TEMPLATE — copy below the last entry:
---
## YYYY-MM-DD — <agent> / <model> (Session N)

- **Flaw:** <what in the protocol or .context_ledger/ system didn't work>
- **Symptom:** <what happened to the agent — the observable friction>
- **Root cause:** <why the protocol/.context_ledger/ let this happen>
- **Suggested fix:** <concrete change to the package — a step, a pitfall,
  a template, a rule>
- **Status:** open | fixed in package <commit-sha or date>
-->

---
## 2026-09-23 — Kofi / deepseek/deepseek-flash (S001)
- **Flaw:** Core 2.0.3 ships two PowerShell ports that no PowerShell engine can
  parse, and `ledger-sync`'s `parse_ports` treats that as a core integrity
  failure — so `verify`, and every gate that calls it, fails on Windows.
- **Symptom:** `sh .context_ledger/core/bin/ledger-sync verify` prints a page of
  parser errors and exits 3 with "PORT PARSE FAILURE" even though `verify_tree`
  (the manifest hash check) passes — the core bytes are exactly the released
  ones.
- **Root cause:** `core/bin/ledger-state.ps1` line 60 interpolates a label
  inside a double-quoted string (`"^\s*[-*]\s*\*\*$Label:\*\*\s*(.*)$"`), which
  both Windows PowerShell 5.1 and pwsh 7 reject as an invalid variable
  reference (the parser reads `$Label:` as a scope-qualified name);
  `ledger-mem.ps1` additionally fails 5.1 parsing. The ports cannot be executed
  on the authoring host (the package CHANGELOG notes the Mac has no pwsh), so
  the syntax errors shipped. Compounding it, `parse_ports` prefers
  `powershell` (5.1, present on every Windows box) over `pwsh`, so any PS7-only
  construct is reported as a defect even on machines that have the right
  engine.
- **Suggested fix:** In `ledger-state.ps1`, use `$($Label)` (or a single-quoted
  format string) instead of `$Label:` inside the double-quoted pattern; make
  the ports 5.1-clean or declare PS7 as the requirement; have `parse_ports`
  prefer `pwsh`, report which engine it used, and skip the ps1 check with a
  clear notice when only a too-old engine is present. Add a Windows parse smoke
  test to the release checklist.
- **Status:** open

---
## 2026-09-23 — Kofi / deepseek/deepseek-flash (S001)
- **Flaw:** A CRLF-only checkout mismatch is reported as "core/ does not match
  its manifest … Do not 'fix' core in place", and the suggested remedy
  (`rollback`) does not fix it — the manifest is correct and the working-tree
  bytes are the problem.
- **Symptom:** On Windows, `verify` listed 20 of the core's files as FAILED;
  for every one of them the manifest hash matched the git blob's LF bytes
  exactly, and `git checkout -- .context/core/` silently did nothing because
  `git status` reported the tree clean (stale stat cache: git never re-hashed
  the CRLF worktree copies). Deleting the files and re-checking them out
  restored LF, and the same verify then reported `core OK`.
- **Root cause:** The pre-2.x core was hashed over LF bytes but shipped no
  recursive `.gitattributes`, so a Windows checkout (global
  `core.autocrlf=true`) could produce CRLF copies that `git status` did not
  report as modified. The failure message assumes tampering and points at
  `rollback`, neither of which fits an EOL-only mismatch.
- **Suggested fix:** Detect an EOL-only mismatch in `verify` (compare against
  the same file with CRLF stripped) and report "CRLF checkout — delete and
  re-checkout the file, or re-run `migrate` to LF-normalize" instead of the
  hand-edited-core message. Core 2.0.3 already ships the recursive
  `.gitattributes` that prevents the situation; the diagnostic stays misleading
  for projects that arrive with legacy CRLF blobs.
- **Status:** open
