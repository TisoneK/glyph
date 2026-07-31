# Current Task (overwrite each session)

Holds exactly one task — the one being worked on right now. Set it at
session start (protocol Step 3), clear it at session end (Step 15). If
you find a stale in-progress entry here, a prior session died mid-task —
check its session entry and backlog before starting.

<!-- TEMPLATE — replace everything below this comment:
- **Session:** YYYY-MM-DD — <agent> / <model>
- **Task:** <what is being worked on right now>
- **Status:** in-progress | done | blocked (<blocker>)
-->

- **Session:** 2026-07-31 — Session 19 — Super Z / unknown (cloud sandbox, Python 3.12.13)
- **Task:** Research + plan Browse Mode (`--browse` flag for `glyph run live <target>`)
  — a visible, user-driven browser that captures auth/payment/login/deposit/withdrawal
  flows the auto-explore path misses. Research complete; ADR-13 (proposed) appended;
  review note written; backlog items added for the build session. **Implementation
  deferred to the next session** per the user's explicit framing ("Do research how we
  will accomplish this").
- **Status:** done (research + planning). Build session = next.
- **Deliverables:**
  - `.context/memory/reviews/2026-07-31-browse-mode-research.md` (the research note)
  - `.context/memory/plans/decisions.md` — ADR-13 (proposed) appended
  - `.context/memory/tasks/backlog.md` — 6 build-session items appended
  - `.context/memory/agents/sessions.md` — Session 19 entry appended
- **Open questions for the user** (carried into the build session, do NOT guess):
  1. TUI in browse mode: browser-only + dashboard after close / split-pane / no dashboard?
  2. Profile persistence: persistent by default + `--incognito`, OR incognito by default + `--profile`?
  3. Closing signal: browser-close only, OR also Ctrl+C as fallback?
  4. Record the request side too (`page.on("request")`)? (Recommend yes.)
  5. Cookie snapshot storage: meta blob (v1) vs dedicated `cookies` table (v2)?
