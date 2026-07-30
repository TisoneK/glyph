# Glyph

A standalone, general-purpose **reverse-engineering toolkit**. Point it at a target —
a web app, a JSON/gRPC API, a mobile app, a data feed — and it does the mechanical work
of discovering, capturing, decoding, and documenting that target's surface, so a human
only has to confirm the ambiguous parts.

The name: the tool decodes a target's opaque symbols (codes, ids, enums) into meaning,
the way a glyph is a mark that carries meaning once you can read it.

**Status:** research / exploration. The full scope, technique catalog, architecture, and
phasing live in **[RESEARCH.md](RESEARCH.md)**.

## Out of scope

- **Tunneling / relay routing** → owned by the separate **InjectX** project. Glyph
  discovers and decodes; it does not route traffic.
- **Evasion & fraud** → Glyph *characterizes* a surface; it does not defeat
  bot-management, solve CAPTCHAs, or bypass access controls. On payments it decodes
  integration surfaces only — never handling real card/credential values, never bypassing
  or manipulating a payment.

## Working with this repo

This repo uses the `.context/` protocol — persistent agent memory plus a vendored copy of
the workflow, committed to git. Any agent starts at
**[.context/kickoff.md](.context/kickoff.md)**.
