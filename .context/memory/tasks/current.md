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

- **Session:** 2026-07-31 — Session 19 (cont.) — Super Z / unknown (cloud sandbox, Python 3.12.13)
- **Task:** Research + plan Browse Mode (`--browse` flag for `glyph run live <target>`).
  Refined after user feedback: **CDP-attach to the user's real browser (Brave primary,
  Edge secondary — both Chromium) is PRIMARY; Playwright-launched real-browser binary is
  FALLBACK.** ADR-14 (proposed) supersedes ADR-13's primary technique. Implementation
  deferred to the build session per the user's "Do research" framing.
- **Status:** done (research + planning, refined). Build session = next.
- **Deliverables:**
  - `.context/memory/reviews/2026-07-31-browse-mode-research.md` — research note (+ section 7: real-browser analysis)
  - `.context/memory/plans/decisions.md` — ADR-13 (superseded, kept for trail) + ADR-14 (proposed, authoritative)
  - `.context/memory/tasks/backlog.md` — 6 ADR-13 build items + 5 ADR-14 build items (the ADR-14 set is authoritative)
  - `.context/memory/agents/sessions.md` — Session 19 entry + Session 19 cont. update
- **Authoritative decision for the build session:** ADR-14. Read ADR-14, NOT ADR-13.
  ADR-13's `launch_persistent_context` is retained as the FALLBACK inside ADR-14.
- **Open questions for the user** (build session must NOT guess — ask):
  1. TUI in browse mode: browser-only + dashboard after detach/close (recommended) / split-pane / no dashboard?
  2. ~~Profile persistence~~ ANSWERED: CDP-attach to real browser is primary (their real session); launch fallback uses dedicated Glyph profile.
  3. Stop signal: CDP-attach → Ctrl+C detaches (browser stays open); launch → close browser or Ctrl+C. (Partially answered — confirm Ctrl+C is primary in attach mode.)
  4. Record the request side too (`page.on("request")`)? (Recommend yes.)
  5. Cookie snapshot storage: meta blob (v1) vs dedicated `cookies` table (v2)?
  6. NEW: should Glyph offer `glyph browse --launch <browser>` to spawn the browser with `--remote-debugging-port`? (Recommend yes, with manual path documented.)
  7. ~~Capture scoping in CDP-attach mode~~ ANSWERED by the user ("it needs target so that we can easily filter non-relevant tabs or targets" + "If target is not specified it captures every traffic"): the target `<url>` is OPTIONAL — present = target-tab + popups (filtered by tab lineage); absent = all-traffic (hook every tab via `context.pages` + `context.on("page")`, stderr banner warning). See ADR-14 point 7.
