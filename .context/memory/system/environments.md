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
## bao@local (macOS) (last verified 2026-08-01)
- **Identify by:** `$USER` = bao; repo path `~/Code/glyph`. NOTE: "bao" is the
  macOS ACCOUNT name (hostname `Baos-Mac-mini`); the USER is **Tisone Kironget**
  (see `user/identity.md`) — never conflate the account name with the person.
- **OS:** macOS (Darwin 24.6.0)
- **Runtimes:** system `python3` = **3.9.6** at `/usr/bin/python3` (no pyenv) — this is only what's *currently installed*. **The user's preferred target is Python 3.13** (stable on Windows, no platform issues; see `user/preferences.md` → Runtime & tooling). The base package was written 3.9-compatible (`from __future__ import annotations` + `typing` imports) as a stopgap; a retarget to 3.13 (+ Pydantic models) is a pending decision. Next session: check whether 3.13 is installed (`python3.13 --version`) before assuming 3.9.
- **Package manager:** `pip` via a project venv at `.venv/` (gitignored). Create with `python3 -m venv .venv`; install with `.venv/bin/python -m pip install -e '.[dev]'`.
- **Verified commands (2026-08-01):**
  - `python3 -m venv .venv && .venv/bin/python -m pip install -e . pytest` — clean install of `glyph-re` (pure-stdlib base) + pytest
  - `.venv/bin/python -m pip install -e '.[dev]'` → **succeeds on this Mac** (Session 21; after the mitmproxy floor fix). Installs mitmproxy 9.0.1 (the last Python-3.9-compatible release), playwright 1.60.0, duckdb 1.4.5, pycryptodome, genson, textual, rich. NOTE: mitmproxy 10+ needs Python >=3.10 so pip pins 9.0.1 here; the Windows box (3.14) gets the latest.
  - `.venv/bin/python -m pytest -q` → **159 passed, 5 skipped** (Session 21; up from 156/8 — playwright now installed so the 4 browse tests run+pass, and the graceful-without-playwright test now skips)
  - `.venv/bin/python -m pytest tests/test_tui.py tests/test_capture_live.py tests/test_capture.py tests/test_cli.py -q` → 37 passed, 4 skipped
  - `sh .context/core/bin/context-sync verify` → `core OK ... (0.5.0)`; `status` → up to date
  - `.venv/bin/glyph --version` → `glyph 0.1.0` (console script installs)
  - `python3 -m glyph.cli ...` runs without install when `PYTHONPATH=<repo>` is set
  - `git` with the `osxkeychain` credential helper — commit + push to `origin` work
- **Quirks:**
  - **`.venv` now has the FULL dev extra** (playwright + mitmproxy + duckdb + pycryptodome since Session 21). Live browser capture can now run on this Mac — but note `playwright install chromium` (the browser binary) has NOT been run here yet; do that before a live capture.
  - **`$USER` is `bao` (macOS account name; hostname `Baos-Mac-mini`) but the USER is Tisone Kironget** — see the Identify-by note above; never conflate the account name with the person.
  - `gh` CLI is NOT installed; pushes rely on the osxkeychain HTTPS credential helper. System Python is 3.9 — do not rely on 3.10+ syntax.

---
## Z.ai cloud sandbox (Linux) (last verified 2026-07-30)
- **Identify by:** workspace path `/home/z/my-project/glyph` (sandbox; no `~/Code/glyph`); the agent runs as user `z`
- **OS:** Linux (kernel details not probed; `/home/z/my-project` is the agent sandbox root)
- **Runtimes:** `sh` (POSIX, needed for `context-sync`), `git`, `sha256sum` (Linux coreutils — `context-sync verify` works natively, no `shasum` fallback needed), `python3` (3.9.6 system + 3.12.13 + 3.13.5 available; **3.13 venv is NOT installable** — `python3.13-venv` package missing, so tests run on 3.12 in `.venv-312`)
- **Package manager:** `pip` (via venv); the `glyph-re[dev]` extra pulls in mitmproxy 12.2.3, playwright 1.61.0, genson 1.4.0, duckdb 1.5.5, pytest 9.1.1
- **Verified commands (this env, last verified 2026-07-30 across Sessions 2 + 3 + 6):**
  - `sh .context/core/bin/context-sync verify` → `core OK: every file matches MANIFEST.sha256 (0.3.0)`
  - `sh .context/core/bin/context-sync status` → `core: 0.3.0  (.context/core)` / `locked: 0.3.0` / `source: none reachable (no sibling package clone; set CONTEXT_PKG or pass a path) — skipping, this is fine`
  - `date -u +%F` → `2026-07-30` (used for every session entry, report filename, and `verified` field per Pitfall #41)
  - `git clone https://<token>@github.com/TisoneK/glyph.git` then `git remote set-url origin https://github.com/TisoneK/glyph.git` (PAT stripped from `.git/config` immediately after clone, per Step 2)
  - Parallel sub-task pattern via the Task tool: launch 3–5 general-purpose agents in one message, each with a tight research scope; collect results; synthesize in the main agent. Verified Session 3 across 5 clusters (~13k words of research output total).
  - **Live capture works in this sandbox (verified Session 6):** `python3.12 -m venv .venv-312` → `.venv-312/bin/pip install -e ".[dev]"` → `.venv-312/bin/playwright install chromium` (succeeds; chromium 149.0.7827.55) → headless launch + render works. `glyph.capture.driver.capture_url` ran live against linebet.com and captured 20 flows with response bodies + a DOM snapshot. Reusable runner: `scripts/live_capture_run.py`.
  - `.venv-312/bin/pytest -q` → 57 passed (45 unit + 12 real-world integration, Session 6).
- **Quirks:**
  - **No sibling package clone** — `context-sync status` cannot find an update source automatically. To enable auto-update checks, clone `https://github.com/TisoneK/.context.git` as a sibling and set `CONTEXT_PKG` to its path. Not required (sync never fails a session), just noted.
  - **Cloud/sandbox agent** — PAT is required for any push (even though the repo is private-only for clone, every push needs auth here). PAT comes from the user's first chat message; used as a transient `GIT_TOKEN` env var; stripped from `.git/config` after every push; unset in Step 19.
  - **Parallel Task agents can time out on large scopes** — Session 3 Tasks 6 (bot-mgmt + payments) and 7 (competitive landscape) timed out (context deadline exceeded) as single large agents on the default glm-5.2 model. Recovery: split each into tighter-scope sub-tasks and re-launch on the faster `haiku` model — all completed. **Reusable pattern: keep each parallel research agent's scope narrow enough to finish in one tool-call window; prefer 3–4 small agents over 1 large one.**
  - **Write tool JSON-arg length limit** — files >~30 KB can't be written in one Write call. Recovery: write the first part with Write, append subsequent parts with a small Python script via Bash (see `/home/z/my-project/scripts/append_deep_dive_part2.py` / `_part3.py` as the pattern).
  - **Try sandbox capabilities before assuming they fail.** Session 6: I told the user "I can't run `playwright install chromium` reliably in this sandbox (heavy browser-binary download)" without trying. The user pushed back; I tried; it installed cleanly and headless chromium works. **Principle: the cost of trying is seconds; the cost of a wrong assumption is a round-trip.** Verify sandbox capabilities by trying, not by extrapolating from prior restricted-environment experience. Recorded after the Session 6 round-trip.
  - **When a user supplies a HAR, check for response bodies first.** Session 6: the uploaded `betting.xhr` had 116 entries but 0 response bodies (Chrome DevTools "Save all as HAR" sometimes strips content). Run `sum(1 for e in har['log']['entries'] if e['response']['content'].get('text'))` before assuming it's usable; if body-less, tell the user up front with the exact re-export instruction ("Save all as HAR **with content**").
  - **Local agents must NOT absorb this block** — the PAT dance, the `/home/z/my-project/glyph` path, and the cloud-sandbox identity are machine- and agent-type-scoped facts. A local agent reading this block should ignore the PAT instructions and log a flaw if memory tried to enforce them on a local session (Pitfall #43).

---
## bao@local (Windows 10/11, PowerShell 7) (last verified 2026-07-31)
- **Identify by:** hostname/path `C:\Users\tison\Dev\glyph`; agent runs as user `tison`
- **OS:** Windows (win32), PowerShell 7 (`pwsh.exe`)
- **Runtimes:** system `python` = **3.14.2**; project venv at `.venv/` (Python 3.14.2)
- **Package manager:** `pip` via project venv. Install with `.venv\Scripts\pip.exe install -e ".[dev]"`.
- **Verified commands (2026-07-31):**
  - `python -m venv .venv` — creates venv
  - `.venv\Scripts\pip.exe install -e ".[dev]"` — installs glyph-re + mitmproxy + playwright + genson + duckdb + pytest
  - `playwright install chromium` — downloads Chrome for Testing + Headless Shell (succeeds on Windows)
  - `.venv\Scripts\pytest.exe -q` → **93 passed, 1 skipped**
  - `pwsh -File .context/core/bin/context-sync.ps1 verify` — core verify (PowerShell port)
  - `pwsh -File .context/core/bin/context-sync.ps1 status` — core status
  - `git config user.name` / `git config user.email` — already set to `Tisone Kironget` / `tisonkironget@gmail.com`
- **Quirks:**
  - `core.autocrlf=true` causes `.context/core/*` files to be checked out with CRLF on Windows, breaking `context-sync verify` against the LF-only MANIFEST.sha256. Workaround: `git checkout -- .context/core/` after any verify failure (rollback restores LF blobs from git history). `.gitattributes` added with `.context/core/* text eol=lf` to prevent renormalization.
  - `context-sync.ps1` is the Windows port of `context-sync`; use it instead of `sh` on this machine.
  - System Python is 3.14.2 — newer than the project's `>=3.9` requirement; code runs fine.
