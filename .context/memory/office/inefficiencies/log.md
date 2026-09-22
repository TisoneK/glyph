# Inefficiency Log (append-only — real friction only)

Append a block **only when something actually slowed you down** — a clean
session appends nothing (its `agents/sessions.md` entry is the record;
"none this session" blocks are noise, not history). But when something
bit you, the block is mandatory and honest: friction you absorb silently
is friction the next agent hits blind.

Most inefficiencies are project-local (an environment quirk, a one-off
cost) and stay here. When one is actually **protocol-level** — the core
workflow itself made you slower and every project would hit it — mark it
`Upstream: candidate`. `ledger-sync harvest` collects those (and open
`flaws/`) into the package for an upstream fix. Unmarked entries are
never harvested.

Append-only, but compactable — the log never grows without bound:

- **Resolved entries move verbatim** to cold storage: once an entry is
  explicitly marked `RESOLVED` / `superseded` / fixed, cut it unchanged
  into `archive.md` in this directory so startup reads only the live
  entries. Age alone never makes an entry eligible.
- **Repeats roll up:** when 3+ entries describe the same recurring thing
  (same failing tool, same root cause), append ONE consolidated
  `Recurring` entry — the pattern, how many times, the current
  workaround — and move the individual entries verbatim into
  `archive.md`. The live log keeps the pattern, not the repeats.

`ledger-mem prune` reports log sizes, archive-eligible entries (`--list`
names them), and roll-up candidates.

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
## 2026-09-23 — Kofi / deepseek/deepseek-flash (S001)
- **Problem:** On this Windows box, `git status` can report a clean tree while
  the working-tree bytes differ from the index, which makes git's own repair
  commands (`git checkout -- <path>`) silent no-ops.
- **Cost:** One full diagnosis cycle (comparing blob vs worktree vs manifest
  hashes) before the real cause was pinned, plus a second pass after the first
  repair sweep missed one file.
- **Cause:** Git trusts cached stat data for a path (size + mtime) and skips
  re-hashing; when files are replaced by a tool that preserves those fields, or
  after a CRLF-converting checkout, the cache still says "clean" while the
  content differs. `git ls-files --eol` and `git hash-object` show the truth
  that `git status` hides.
- **Workaround / fix:** Delete the affected files, then `git checkout -- <dir>`
  to force a rewrite from the index. Core 2.x's recursive `.gitattributes`
  (`core/** text eol=lf`) keeps future checkouts byte-identical to the
  manifest. Do **not** run `git add --renormalize .` repo-wide on this box: the
  root `.gitattributes` has no `text=auto`, so it would stage CRLF into the
  blobs of ~25 product files instead of normalizing them.
- **Prevent next time:** When an integrity check disagrees with `git status`,
  compare `git ls-files --eol` and `git hash-object <path>` against the index
  before trusting either; treat a stat-cache "clean" as a hint, not evidence.
- **Upstream:** not a protocol issue

---
## 2026-09-23 — Kofi / deepseek/deepseek-flash (S001)
- **Problem:** The sibling package clone (`~/Dev/.context`) was checked out
  before the ledger-tooling work, and `ledger-sync update` installs core by
  copying that working tree byte-for-byte (`cp -R`) rather than from git blobs
  — so any line-ending or staleness defect in the clone's worktree propagates
  straight into the project's core.
- **Cost:** An extra verification pass to rule CRLF out as the cause of the
  parse failure (the clone turned out clean, so the defect was genuinely
  upstream in the release).
- **Cause:** `update` trusts the source tree's working copy; it verifies the
  staged copy against `MANIFEST.sha256` afterwards, but only if the source tree
  itself verified first.
- **Workaround / fix:** Before any `update`, refresh and verify the package
  clone (`git -C ../.context pull --ff-only` and `git -C ../.context status`),
  since a stale or dirty clone becomes the installed core.
- **Prevent next time:** Treat the sibling package clone as a release artifact,
  not a scratch checkout: keep it clean, and let `ledger-sync update` verify it
  before the swap.
- **Upstream:** not a protocol issue
