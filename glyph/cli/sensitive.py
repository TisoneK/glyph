"""`glyph sensitive` — flag sensitive data / endpoints / risk indicators.

Human output is a rich table with **masked** values (enough to identify,
not to leak to a terminal/scrollback). ``--json`` returns the full findings
incl. the raw value (kept at rest per ADR-4).
"""
from __future__ import annotations

import argparse

from glyph.cli import _console as C
from glyph.cli._format import mask_value, sev_line
from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json

_KIND_ALIAS = {"data": "sensitive_data", "endpoints": "sensitive_endpoint",
               "risk": "risk"}


def add_parser(sub) -> None:
    sp = with_json(with_db(sub.add_parser(
        "sensitive", help="flag sensitive data / endpoints / risk indicators")))
    sp.add_argument("--kind", choices=["data", "endpoints", "risk"],
                    help="show only one kind of finding")
    sp.add_argument("--severity", choices=["critical", "high", "medium", "low"],
                    help="show only findings at or above this severity")
    sp.add_argument("--all", action="store_true",
                    help="include tracking/ad hygiene noise too")
    sp.add_argument("--party", choices=["first", "third"],
                    help="show only first- or third-party findings")
    sp.add_argument("--target", metavar="HOST",
                    help="override the primary host that defines first-party")
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.sensitive import run_scan
    from glyph.sensitive.scan import is_noise
    cat = catalog(args)
    try:
        if getattr(args, "target", None):
            cat.set_target(args.target)
        summary = run_scan(cat)
        kind = _KIND_ALIAS.get(args.kind) if args.kind else None
        findings = cat.findings(kind=kind, min_severity=args.severity)
    finally:
        cat.close()

    # Default hides ONLY tracking/ad hygiene noise (never data findings, never
    # generic third-party hosts). --all shows noise; --party filters party.
    if args.party:
        want = {"first": "first_party", "third": "third_party"}[args.party]
        findings = [f for f in findings if f.party == want]
    if not args.all:
        findings = [f for f in findings if not is_noise(f)]

    if args.json:
        emit({"summary": summary,
              "findings": [f.__dict__ for f in findings]}, True)
        return 0

    if C.HAS_RICH:
        _render_rich(summary, findings, args)
    else:
        _render_plain(summary, findings, args)
    return 0


def _rows(findings):
    for f in findings:
        party = {"third_party": "3p", "first_party": "1p"}.get(f.party, "?")
        yield (f, party, "" if f.location == "endpoint" else f.location,
               mask_value(f.value_sample))


def _render_rich(summary, findings, args) -> None:
    con = C.con()
    target = summary.get("target") or "(unknown)"
    noise = summary.get("tracking_noise", 0)
    counts = C.sev_counts(summary.get("actionable_by_severity", {}))
    title = (f"Sensitive findings  ·  [cyan]{target}[/]  ·  "
             f"[bold]{summary['actionable_total']}[/]  {counts}")
    if noise and not args.all:
        title += f"   [grey58](+{noise} tracking noise · --all)[/]"

    if not findings:
        con.print(title)
        con.print("[grey58](no findings match the filter)[/]")
        return

    t = C.table(title=title)
    t.add_column("SEV")
    t.add_column("TYPE")
    t.add_column("P", justify="center")
    t.add_column("HOST", style="cyan", no_wrap=True)
    t.add_column("LOCATION", overflow="fold")
    t.add_column("VALUE", style="grey58", no_wrap=True)
    for f, party, loc, val in _rows(findings):
        t.add_row(C.sev_cell(f.severity), f.category, party, f.host or "", loc, val)
    con.print(t)
    con.print("[grey58](values masked · --json for full values · "
              "--all for tracking noise)[/]")


def _render_plain(summary, findings, args) -> None:
    print(f"target: {summary.get('target') or '(unknown)'}")
    print(f"{summary['actionable_total']} finding(s): "
          f"{sev_line(summary.get('actionable_by_severity', {}))}")
    if not findings:
        print("(no findings match the filter)")
        return
    for f, party, loc, val in _rows(findings):
        loc = f" @ {loc}" if loc else ""
        val = f"  [value: {val}]" if val else ""
        host = f" [{f.host}]" if f.host else ""
        print(f"[{f.severity.upper():8}] {f.category}{loc}{host}{val}")
