# Glyph

A standalone, general-purpose **reverse-engineering toolkit**. Point it at a target —
a web app, a JSON/gRPC API, a mobile app, a data feed — and it does the mechanical work
of discovering, capturing, decoding, and documenting that target's surface, so a human
only has to confirm the ambiguous parts.

The name: the tool decodes a target's opaque symbols (codes, ids, enums) into meaning,
the way a glyph is a mark that carries meaning once you can read it.

**Status:** research / exploration. The full scope, technique catalog, architecture, and
phasing live in **[RESEARCH.md](RESEARCH.md)**.

> **A note on security and payment surfaces** — Glyph defeats anti-bot, CAPTCHA,
> and access-control systems as a natural consequence of decoding them. It handles
> payment-integration surfaces at the protocol/API level (tokenised payloads, not
> raw card values). Credential and card values are never stored or logged.

## Working with this repo

This repo uses the `.context/` protocol — persistent agent memory plus a vendored copy of
the workflow, committed to git. Any agent starts at
**[.context/kickoff.md](.context/kickoff.md)**.
