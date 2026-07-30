# Flaws Log (append-only — flows to the protocol package)

Friction caused by the `.context/` system or the protocol itself. See
`README.md` in this directory for the split between `flaws/` and
`inefficiencies/`.

<!-- TEMPLATE — copy below the last entry:
---
## YYYY-MM-DD — <agent> / <model> (Session N)

- **Flaw:** <what in the protocol or .context/ system didn't work>
- **Symptom:** <what happened to the agent — the observable friction>
- **Root cause:** <why the protocol/.context/ let this happen>
- **Suggested fix:** <concrete change to the package — a step, a pitfall,
  a template, a rule>
- **Status:** open | fixed in package <commit-sha or date>
-->

---
## 2026-07-30 — Super Z / glm-5.2 (Session 3, correction)

- **Flaw:** The cloud edition's Step 2 lists `git config user.name` and `git config user.email` as setup steps after cloning, but does not mark them as critical or verify them before the first commit. A cloud/sandbox agent that skips these two lines (easy to do — they're buried in a 5-line code block alongside the clone and the token-strip) commits with the sandbox's default identity instead of the project's Git identity. The kickoff's "Project Facts" record the correct Git identity, but nothing in the entry steps re-confirms `git config user.email` matches before the agent starts committing.
- **Symptom:** Session 2 and Session 3 both pushed 6 commits to `origin/main` authored as `Z User <z@container>` (the sandbox default) instead of `Tisone Kironget <tisonkironget@gmail.com>` (the project's Git identity per `.context/kickoff.md` Project Facts). The user caught it after Session 3 ("You broke the rules and pushed as Z User instead of setting my git as per protocol"). The fix required a `git filter-branch` history rewrite of 6 commits + a `--force-with-lease` push — destructive, embarrassing, and entirely avoidable.
- **Root cause:** Two compounding gaps:
  1. **Step 2 doesn't emphasize the git-config lines.** The code block reads as "clone, strip token, configure identity" — but the clone and token-strip are the loud parts (security-critical, called out in Pitfalls #13/#19), while the two `git config` lines look like optional housekeeping. An agent skimming Step 2 can easily carry the clone + strip and drop the config.
  2. **No pre-commit verification.** Nothing in the protocol checks `git config user.email` against the Pre-Flight Git Email before the first commit. The quality gates (Quality Gates section) check typecheck/lint/tests/changelog/secrets — but not "are you committing as the right person?" The first place the wrong identity surfaces is the GitHub commit history, which is too late.
- **Suggested fix:** Two concrete changes to the package:
  1. **Add a pitfall** (the cloud edition's Common Pitfalls section): "Don't commit before confirming `git config user.name` and `git config user.email` match the Pre-Flight Git identity. Sandbox/CI environments default to a generic user (e.g., `z@container`) — every commit you make inherits that identity, and fixing it after push requires a history rewrite + force-push. Run `git config user.name && git config user.email` after Step 2 and verify both match before Step 3."
  2. **Add a pre-commit quality gate** (the Quality Gates section): "[ ] `git config user.email` matches the Pre-Flight Git Email (sandbox defaults to a generic user — verify before the first commit, not after the first push)."
- **Status:** open — this flaw affected this project (6 commits rewritten, force-pushed 2026-07-30). Every cloud/sandbox session on a fresh environment will hit it until the package adds the pitfall + the quality gate. Local agents are unaffected (they inherit the user's already-configured git identity).
