# Active Workflow (overwrite when the workflow changes)

The workflow currently in force for this repo.

- **Protocol:** by agent type — local agents → .context/core/rules/ai-engineering-protocol-local.md; cloud/sandbox agents → .context/core/rules/ai-engineering-protocol.md
- **Protocol location:** on disk — vendored in `.context/core/` (version in `.context/core/VERSION`, last verified in `../core.lock`)
- **Package upstream (for flaw back-ports + core updates):** https://github.com/TisoneK/.context.git
- **Since:** 2026-07-29
- **Default role:** engineer — unless a session says otherwise; see .context/core/roles/
- **Scope:** research / exploration phase — shape the tool (features, techniques, architecture) as docs; no build yet
- **Target:** free text per session (bootstrap session: initialize .context + land RESEARCH.md)
- **Focus areas:** architecture, technique coverage, scope boundaries
- **Findings handling:** fix safe; flag scope/design decisions for the user
- **Push policy:** push to main directly after each logical commit
- **Commit style:** Conventional Commits with scope; `chore(context):` for `.context/`
- **Commit granularity:** one logical change per commit; never mix product + `.context` surfaces
- **Deliverable:** docs (RESEARCH.md + ADRs) + chat summary
