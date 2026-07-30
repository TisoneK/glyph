# User Preferences (update in place)

How the user likes things done **on this project**. Seeded from
Pre-Flight at bootstrap; grows as sessions reveal preferences.

## Workflow
- Follow the `.context/` protocol: ADRs + docs alongside implementation; commit and push each logical change. (pre-flight)
- New systems start research-first — shape scope, features, and boundaries as a doc before building. (approved pattern, 2026-07-29)

## Communication
- Chat summaries in plain language; keep the technical depth in the docs/reports. (stated, 2026-07-29)

## Code style
- Prefer modular packages over one long file — split code into focused
  modules/subpackages; a single long file is "unmaintainable." (stated,
  2026-07-30) Applied: `glyph/` is one subpackage per pipeline stage.

## Review depth

## Risk & approvals
- Naming and scope are the user's call — judge a name on its own merit; do NOT couple a standalone tool to sibling projects. (correction, 2026-07-29)
