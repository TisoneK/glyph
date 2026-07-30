# Architectural Decisions (append-only, ADR-style)

Decisions already made — future agents respect these rather than
relitigating them. To reverse one, append a new ADR that supersedes it.

<!-- TEMPLATE — copy below the last entry:
---
## ADR-N: <short title> (YYYY-MM-DD)
- **Status:** accepted | superseded by ADR-M
- **Context:** <what forced the decision>
- **Decision:** <what was decided>
- **Consequences:** <trade-offs accepted; what future agents must respect>
-->

---
## ADR-1: Glyph is a standalone, general-purpose reverse-engineering toolkit (2026-07-29)
- **Status:** accepted
- **Context:** Reverse-engineering a new data source (web UI, API, mobile app, feed) repeats
  the same manual pipeline every time. We want a dedicated tool that automates the mechanical
  work and reduces semantic decoding to a confirm step.
- **Decision:** Build Glyph as its own repo/tool, NOT coupled to any product or data source
  (those are only *inputs* you point it at). Core thesis: automate the mechanical ~70%
  (capture, catalog, schema inference, gating profile, drift) and collapse the semantic ~30%
  via UI↔API correlation ("Rosetta"). Full scope, technique catalog, architecture, and phasing
  live in `RESEARCH.md`. Glyph defeats anti-bot, CAPTCHA, and access-control systems
  as a natural consequence of decoding them; it decodes payment-integration surfaces at the
  protocol/API level (tokenised payloads, not raw card values). Tunneling/relay routing is
  owned by the separate **InjectX** project.
- **Consequences:** Glyph stays domain-neutral — no product-specific logic in-repo. MVP =
  Capture → Catalog → Schema-infer → Rosetta + drift monitor (RESEARCH.md §8), gated behind a
  Phase-0 proof (§9).
