# Session Review / Handoff — CLI UX improvements + cli/ package split (Session 11)

- **Date:** 2026-07-31
- **Agent:** Claude Code / claude-opus-4-8 (local, bao@local Windows)
- **Role:** engineer | **Core:** 0.4.0

## Problem statement

Two UX gaps surfaced during environment setup on Windows:

1. **Inconsistent empty-state messaging.** `glyph run live` reports `rosetta: 0 decoded` (meaning rosetta ran and found nothing), but `glyph dict` says `(dictionary empty — run 'glyph rosetta' first)`, implying rosetta never ran. The user has no way to tell whether rosetta needs to be re-run or legitimately found 0 candidates.

2. **Sensitive findings are invisible.** `glyph sensitive` outputs only a count line (`sensitive: 10 finding(s) (2 medium, 8 low)`). The actual data is hidden — the user must run a separate command and hope it's more useful.

## Proposed fixes

### 1. Fix empty-state consistency in `glyph dict`

`glyph dict` must distinguish three states:

| State | Current output | Proposed output |
|-------|---------------|-----------------|
| Rosetta ran, 0 candidates | `(dictionary empty — run 'glyph rosetta' first)` | `(no fields decoded — 0 candidates found by rosetta, see 'glyph rosetta --verbose')` |
| Rosetta never ran | same as above | `(dictionary empty — rosetta has not run yet. Run 'glyph rosetta' or 'glyph run live' first.)` |
| Rosetta ran, found entries | shows entries | shows entries (no change) |

Add a one-line hint about why 0 fields were found when schema also reports 0:
```
schema: 0 fields, 0 enum candidates
rosetta: 0 decoded (0 high-confidence, 0 to review)
         ↳ no structured request/response bodies found in captured flows
```

This requires `glyph dict` to read the last pipeline run metadata from the catalog (timestamp, result counts) rather than just checking whether any dictionary rows exist.

### 2. Table output for `glyph sensitive`

Replace the count-only summary with a masked, color-coded table:

```
$ glyph sensitive

  #   SEVERITY   TYPE            LOCATION                  VALUE
  1   medium     api_key         script #3, query param    sk_live_***3f2a
  2   medium     email           document #2, JSON body    j***@example.com
  3   low        session_id      script #1, cookie          ses_***9b21
  4   low        ip_address      document #4, header       192.168.*.*
  ...
  10  low        user_agent      script #4, header          Mozilla/5.0 (Win...)

  10 findings — 2 medium, 8 low
  filter: --severity medium | --type api_key | --flow 3
```

Principles:
- **Mask by default, don't redact.** Show enough to identify (`sk_live_***3f2a`, not `[REDACTED]`). For an RE tool, the value is the point.
- **Precise location.** Which flow #, which part (header/body/query/cookie), which field name.
- **Severity color-coding.** Red for critical/high, yellow for medium, dim for low.
- **Filter flags.** `--severity`, `--type`, `--flow N` for narrowing.
- **`--json` for scripting.** Pretty table for humans, JSON for automation.

### 3. Split `cli.py` into a `cli/` package

`glyph/cli.py` is ~517 lines with 12+ subcommands. The formatting and flag logic for `sensitive`, `dict`, and `rosetta` will each grow. A package split now is cheaper than retrofitting later.

Proposed structure:

```
glyph/cli/
  __init__.py     # entry point, top-level parser, subcommand registration
  run.py          # `glyph run live/har`
  dict.py         # `glyph dict`
  rosetta.py      # `glyph rosetta`
  sensitive.py    # `glyph sensitive` — table rendering, masking, filters
  codegen.py      # `glyph codegen`
  catalog.py      # `glyph catalog`
  _format.py      # shared table/color/mask helpers
  _output.py      # shared --json vs human-output switch
```

Principles:
- One file per subcommand, each exposing `add_parser(subparsers)` + `run(args)`.
- Shared formatting in `_format.py` — same table look across `sensitive`, `dict`, `schema`.
- Shared output mode in `_output.py` — `--json` vs human is a decision every command opts into the same way.
- Business logic stays in stage modules — `cli/sensitive.py` calls into `glyph.sensitive` and handles presentation only.

## ADR

Recorded as **ADR-5** in `.context/memory/plans/decisions.md`:

> Split `cli.py` into a `cli/` package; table rendering + masking for sensitive output.

Status: **proposed** — awaiting implementation.

## Next steps

1. Fix `glyph dict` empty-state messaging first (small, isolated change in current `cli.py`).
2. Add table rendering + masking for `glyph sensitive` (can be done in current `cli.py` or as part of the split).
3. Split `cli.py` into `cli/` package (structural, can be done incrementally — move one subcommand at a time).
4. Add `--json` output mode to `glyph sensitive` (after the table works).
