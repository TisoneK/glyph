# Environments (update in place)

Machines and sandboxes agents have run on, and what it takes to work on
this project from each. One block per environment; update the matching
block (and its "last verified" date) every time you run on it again.

## Rules

1. **Match before you add.** At session start, check whether the machine
   you're on already has a block (use its "Identify by" line). Update the
   match; add a new block only for a genuinely new environment.
2. **Record what you verified, not what you assume.** A command belongs
   under "Verified commands" only after it ran successfully on this
   environment, this project.
3. **Agents never delete blocks.** An environment the project no longer
   uses may be pruned by the user; if you can't verify a block, leave it
   alone — its last-verified date already says how stale it is.
4. **Machine facts only.** Secret values go in `secrets/`; user
   preferences in `user/`; project-wide decisions in `plans/`.

<!-- TEMPLATE — one block per environment:
---
## <stable label — hostname, "Z sandbox", "GitHub Actions ubuntu-24.04"> (last verified YYYY-MM-DD)
- **Identify by:** <how an agent recognizes this env — hostname, $USER, workspace path>
- **OS:** <e.g., macOS 15.5 / Ubuntu 24.04 sandbox>
- **Runtimes:** <node X, python Y, ...>
- **Package manager:** <npm/bun/pnpm/pip/...>
- **Verified commands:** <install / test / lint / typecheck / dev-server commands that actually worked here, with cwd if it matters>
- **Quirks:** <e.g., "no psql installed", "port 3000 usually taken", "system Python locked down">
-->

---
## bao@local (macOS) (last verified 2026-07-29)
- **Identify by:** `$USER` = bao; repo path `~/Code/glyph`
- **OS:** macOS (Darwin 24.6.0)
- **Runtimes:** none required yet (research phase)
- **Package manager:** — (TBD once a build starts)
- **Verified commands:** `git` with the `osxkeychain` credential helper — commit + push to `origin` work
- **Quirks:** `gh` CLI is NOT installed; pushes rely on the osxkeychain HTTPS credential helper

---
## Z.ai cloud sandbox (Linux) (last verified 2026-07-30)
- **Identify by:** workspace path `/home/z/my-project/glyph` (sandbox; no `~/Code/glyph`); the agent runs as user `z`
- **OS:** Linux (kernel details not probed; `/home/z/my-project` is the agent sandbox root)
- **Runtimes:** `sh` (POSIX, needed for `context-sync`), `git`, `sha256sum` (Linux coreutils — `context-sync verify` works natively, no `shasum` fallback needed)
- **Package manager:** — (TBD; no product code yet)
- **Verified commands (this session, this env):**
  - `sh .context/core/bin/context-sync verify` → `core OK: every file matches MANIFEST.sha256 (0.3.0)`
  - `sh .context/core/bin/context-sync status` → `core: 0.3.0  (.context/core)` / `locked: 0.3.0` / `source: none reachable (no sibling package clone; set CONTEXT_PKG or pass a path) — skipping, this is fine`
  - `date -u +%F` → `2026-07-30` (used for every session entry, report filename, and `verified` field per Pitfall #41)
  - `git clone https://<token>@github.com/TisoneK/glyph.git` then `git remote set-url origin https://github.com/TisoneK/glyph.git` (PAT stripped from `.git/config` immediately after clone, per Step 2)
- **Quirks:**
  - **No sibling package clone** — `context-sync status` cannot find an update source automatically. To enable auto-update checks, clone `https://github.com/TisoneK/.context.git` as a sibling and set `CONTEXT_PKG` to its path. Not required (sync never fails a session), just noted.
  - **Cloud/sandbox agent** — PAT is required for any push (even though the repo is private-only for clone, every push needs auth here). PAT comes from the user's first chat message; used as a transient `GIT_TOKEN` env var; stripped from `.git/config` after every push; unset in Step 19.
  - **Local agents must NOT absorb this block** — the PAT dance, the `/home/z/my-project/glyph` path, and the cloud-sandbox identity are machine- and agent-type-scoped facts. A local agent reading this block should ignore the PAT instructions and log a flaw if memory tried to enforce them on a local session (Pitfall #43).
