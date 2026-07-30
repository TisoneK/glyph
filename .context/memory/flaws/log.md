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

---
## 2026-07-31 — Super Z / glm-5.2 (Session 8)

- **Flaw:** The protocol assumes the package is always >= the project (sync direction: package → project). It has no defined behavior when a project's vendored core is NEWER than the package upstream — `context-sync status` reports "source is OLDER than local; nothing to do" and `context-sync update` refuses to downgrade, but nothing flags this as the divergence it is, and nothing reconciles it.
- **Symptom:** Session 8 sync attempt. This project's `.context/core/VERSION` is 0.3.0 (the "harvest release" — adds `context-sync harvest`, `fleet.md`, `inbox/`, the `[core-defect]`/`Upstream: candidate` schema fields; `context-sync` is 407 lines). The package upstream (`github.com/TisoneK/.context.git` HEAD `72c5b5a`) is 0.2.0 (269-line `context-sync`, no harvest command). The 0.3.0 release was developed and landed in this project's vendored core but was never pushed to the package upstream — the package's latest commit even says "0.3.0 target" but its `core/VERSION` file is still 0.2.0 and the harvest-release code isn't there.
- **Root cause:** The release workflow has no enforcement that a core version bump in a project's vendored copy must be accompanied by a push to the package upstream. `context-sync manifest` (which regenerates `MANIFEST.sha256` for a new release) runs in package mode, but nothing forces the package maintainer to actually commit + tag + push the release. The project's 0.3.0 core is effectively an unreleased dev version that escaped into a downstream project without the package catching up.
- **Suggested fix:** Two concrete changes to the package:
  1. **`context-sync status` should warn on project-ahead-of-package.** Currently it says "source is OLDER than local; nothing to do" and treats that as a clean state. It should instead emit a prominent WARNING: "local core (0.3.0) is NEWER than the package upstream (0.2.0) — the package is behind. The project's core has features the package lacks. Run `context-sync publish` (new command) to push the project's core back to the package, or accept the divergence." The current "nothing to do" framing hides a real problem.
  2. **Add a `context-sync publish` command (package mode, reverse direction).** When a project's core is ahead of the package, `publish` copies the project's `core/` back to the package clone, regenerates the manifest, commits as `chore(context): release <version>`, and pushes. This closes the reverse-direction gap the current one-way sync can't. (The `harvest` command already does the reverse direction for memory flows; `publish` would do it for core itself.)
  3. **Make `context-sync manifest` refuse to run in project mode.** Currently `manifest` is `need_package` only, which is correct — but a project that bumped its own `core/VERSION` (as happened here) has no way to regenerate its own `MANIFEST.sha256` if it hand-edited core. The 0.3.0 release in this project DID regenerate the manifest (verify passes), so this isn't the immediate bug — but the release process that put 0.3.0 here without pushing to the package is the gap.
- **Status:** open — affects this project (0.3.0 vs 0.2.0 divergence). The project's 0.3.0 core works correctly (verify passes, harvest is functional, the `[core-defect]` override from Session 2 is in place for upstream harvest). But the package upstream is behind, so the next project bootstrapped from the package would get 0.2.0 and miss the harvest release entirely. **Action for the user (package maintainer):** push the 0.3.0 release to `github.com/TisoneK/.context.git` — bump `core/VERSION` to 0.3.0, ensure the harvest-release code is present, regenerate `MANIFEST.sha256`, commit as `chore(context): release 0.3.0`, tag `v0.3.0`, push.
