# Active Workflow (overwrite when the workflow changes)

The workflow currently in force for this repo.

- **Protocol:** by agent type — local agents → .context/core/rules/ai-engineering-protocol-local.md; cloud/sandbox agents → .context/core/rules/ai-engineering-protocol.md
- **Protocol location:** on disk — vendored in `.context/core/` (version in `.context/core/VERSION`, last verified in `../core.lock`)
- **Package upstream (for flaw back-ports + core updates):** https://github.com/TisoneK/.context.git
- **Since:** 2026-07-30 (build phase; research phase ran 2026-07-29 → 2026-07-30)
- **Default role:** engineer — unless a session says otherwise; see .context/core/roles/
- **Scope:** build phase — implement the general-purpose Glyph package (composable stages over a shared catalog). Research canon (RESEARCH.md + RESEARCH-DEEP-DIVE.md) is settled; ADR-2 fixes the architecture, ADR-3 makes Glyph fully standalone.
- **Target:** free text per session; user directive 2026-07-30 = "build everything, general-purpose, no specific target"
- **Focus areas:** correctness of the core pipeline (catalog → capture → schema → rosetta), general-purpose interfaces, test coverage, no coupling to sibling projects
- **Findings handling:** fix safe; flag scope/design decisions for the user
- **Push policy:** push to main directly after each logical commit
- **Commit style:** Conventional Commits with scope; `chore(context):` for `.context/`
- **Commit granularity:** one logical change per commit; never mix product + `.context` surfaces
- **Deliverable:** working `glyph` Python package (installable, tested) + chat summary
