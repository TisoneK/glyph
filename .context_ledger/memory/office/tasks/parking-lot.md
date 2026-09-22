# Parking Lot (deferred knowledge — not a queue)

The backlog is a work queue you act on; this file is the knowledge base
you **don't** act on yet. Research findings, open design questions,
advisory "should we…?" items, deferred work, and someday ideas live here
so the backlog stays a queue an agent can actually work from. Nothing
here is urgent, nothing here is capped, and nothing here blocks a gate.
The record of a finding is its own row plus the commit / session entry
that produced it; git history keeps every row, so promoting or dropping
one loses nothing.

**One rule keeps the two files honest: a parking-lot row is not a task.**
If an item becomes actionable — it now has a clear next step and someone
to take it — **promote** it: cut the row here, add an actionable row to
`backlog.md` (a fresh `B-` ID, one line, pointing back at this row's `P-`
ID if the context matters), and leave it here only as a one-line
"→ promoted to B-… " stub if you want the breadcrumb. An item that turns
out to be wrong or moot is just deleted — history remembers it.

Every row gets a stable **ID** — `P-<added YYYY-MM-DD>-<n>`, n = that
date's next sequence in the file — and a **Summary** cell with enough
context that a future session can pick it up cold. Keep status
qualifiers in the text ("advisory", "needs a decision", "blocked on X",
"deferred by owner"). There is **no cap** here and **no priority** —
items are grouped by *kind*, because the whole point is that these are
not competing for the top of a queue.

This file belongs to the **current office**. When the office closes, the
parking lot is **not** re-seeded wholesale: the closing session promotes
what is now actionable into the new backlog and records the rest in the
permanent record (`history/office-<NNN>.md`, "Open threads"). A cold
idea earns its way into the next office by becoming work, not by being
copied.

Full spec: `.context_ledger/core/schemas/ledger-schema.md` →
"The parking lot".

## Findings

What we learned that isn't work yet — observations, measurements, root
causes, "the current design does X because Y".

| ID | Summary |
|----|---------|
| P-2026-09-23-1 | **Windows CRLF + stale stat cache.** A checkout can leave CRLF copies of core files while `git status` still reports the tree clean, so `ledger-sync verify` fails on every file and `git checkout -- .context_ledger/core` silently does nothing (git trusts the cached stat, never re-hashes). Delete-then-checkout restores LF; the recursive `.gitattributes` installed by core 2.x prevents recurrence. Diagnosed by proving the manifest hash matched the LF blob while the worktree bytes were CRLF. |
| P-2026-09-23-2 | **`git add --renormalize .` is unsafe repo-wide here.** The root `.gitattributes` has no `text=auto`, so a global renormalize would stage CRLF into the blobs of ~25 product files (any path without an `eol=lf` attribute) instead of normalizing them. Normalize per path, or add a real repo-wide policy first. |

## Open questions

Advisory questions, decisions still up for grabs, "should we…?" — a
question is not a task until it has an owner and a next step (then it
becomes a backlog row or an ADR in `plans/decisions.md`).

| ID | Summary |
|----|---------|
| P-2026-09-23-3 | **Retarget the base package to Python 3.13 + Pydantic?** The user prefers 3.13 (stable on Windows) and Pydantic as the model layer; the package was written 3.9-compatible with stdlib dataclasses as a stopgap because 3.9 was the only interpreter on the macOS box. Adopting Pydantic makes it a hard dependency, which reopens ADR-2's "zero required dependencies" base. Needs a decision before the next schema-heavy stage. |

## Deferred work

Real tasks, consciously parked — not now, but keepable. This is where a
backlog row goes when the cap forces a prune and the item still matters:
out of the queue, not into the void.

| ID | Summary |
|----|---------|
| P-2026-09-23-4 | **DuckDB catalog backend.** The catalog is SQLite today; a DuckDB backend was considered for analytical queries over large captures and consciously deferred. Revisit when a capture is big enough that SQLite aggregation is the bottleneck. |
| P-2026-09-23-5 | **`glyph capture proxy` (mitmproxy) for Firefox/Safari.** CDP attach is Chromium-only, so non-Chromium users have no browse-mode path (they use `glyph run har`). The command would start `mitmdump -s glyph/capture/mitm.py`, add a websocket handler, and document browser-proxy + cert install per browser — roughly 100–150 LOC. Parked until a Firefox/Safari user asks for it. |

## Someday

Loose ideas with no owner and no hook yet. The lowest-pressure shelf.

| ID | Summary |
|----|---------|

<!-- TEMPLATE — add one row to the matching section:
| P-<YYYY-MM-DD>-<n> | <enough context that a future session can pick
      this up cold — status qualifiers in the text; promote to the
      backlog when it becomes actionable> |
-->
