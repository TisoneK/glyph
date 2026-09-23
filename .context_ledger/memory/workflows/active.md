# Active Workflow (overwrite when the workflow changes)

The workflow currently in force for this repo.

- **Protocol:** by agent type — local agents → `.context_ledger/core/rules/ai-engineering-protocol-local.md`; cloud/sandbox agents → `.context_ledger/core/rules/ai-engineering-protocol.md`
- **Protocol location:** on disk — vendored in `.context_ledger/core/` (version in `.context_ledger/core/VERSION`, last verified in `memory/core.lock`)
- **Package upstream (for flaw back-ports + core updates):** https://github.com/TisoneK/.context.git
- **Since:** 2026-07-30 (build phase; research phase ran 2026-07-29 → 2026-07-30). Core migrated 0.8.0 → 2.0.3, `.context/` → `.context_ledger/`, on 2026-09-23.
- **Default role:** engineer — unless a session says otherwise; see `.context_ledger/core/roles/`
- **Scope:** build phase — implement the general-purpose Glyph package (composable stages over a shared catalog). Research canon (RESEARCH.md + RESEARCH-DEEP-DIVE.md) is settled; ADR-2 fixes the architecture, ADR-3 makes Glyph fully standalone.
- **Target:** free text per session; user directive 2026-07-30 = "build everything, general-purpose, no specific target"
- **Focus areas:** correctness of the core pipeline (catalog → capture → schema → rosetta), general-purpose interfaces, test coverage, no coupling to sibling projects
- **Findings handling:** fix safe; flag scope/design decisions for the user
- **Push policy:** push to main directly after each logical commit
- **Commit style:** Conventional Commits with scope; `chore(ledger):` for `.context_ledger/`
- **Commit granularity:** one logical change per commit; never mix product + `.context_ledger` surfaces
- **Deliverable:** working `glyph` Python package (installable, tested) + chat summary
- **Core:** 2.0.4 — `ledger-sync verify` passes on this Windows box (manifest match plus every port parsing under both PowerShell 5.1 and pwsh 7). The 2.0.3 port defect and the `[core-defect]` override it needed are retired.
