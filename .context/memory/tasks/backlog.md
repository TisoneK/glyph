# Backlog (append-only)

Open items for future sessions. Append at the bottom; never delete or
reorder. When an item is done, check it off and note the session/commit —
don't remove the line.

<!-- TEMPLATE — copy below the last entry:
---
- [ ] **<short title>** (added YYYY-MM-DD by <agent>) — <enough context that
      a fresh agent can act on this without any chat history. Severity if known.>
-->

---
- [ ] **Build MVP: pipeline stages 1–4 + drift monitor** (added 2026-07-29 by Claude Code) —
      Capture → Catalog → Schema-infer → Rosetta (UI↔API correlation), plus the drift
      monitor. See RESEARCH.md §4/§6a/§8. This is the core that turns a browsing session
      into a documented, semantically-decoded catalog. High.
- [ ] **Phase-0 proof** (added 2026-07-29 by Claude Code) — run stages 1–4 against any
      target with opaque codes + a visible UI; have Rosetta auto-derive its code dictionary
      and check it reproduces hand-analysis. RESEARCH.md §9. Gate for building the rest.
- [x] **Decide repo/service split + catalog store** (added 2026-07-29 by Claude Code;
      done 2026-07-30 by Claude Code, ADR-2) — resolved: monorepo, stages as packages,
      catalog as a library, SQLite → DuckDB → Postgres. See `plans/decisions.md` ADR-2.
- [ ] **README: proposed repo/package layout** (added 2026-07-29 by Claude Code) —
      flesh the repo structure once §11 is decided. Low.
