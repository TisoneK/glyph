"""`glyph sensitive` — flag sensitive data / endpoints / risk indicators.

Human output is a scannable table with **masked** values (enough to
identify, not to leak to a terminal/scrollback). `--json` returns the full
findings incl. the raw value (kept at rest per ADR-4).
"""
from __future__ import annotations

import argparse

from glyph.cli._format import label, mask_value, sev_label, sev_line, style, table
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

    noise = summary.get("tracking_noise", 0)
    head = (f"{label(str(summary['actionable_total']) + ' finding(s)')}: "
            f"{sev_line(summary.get('actionable_by_severity', {}))}")
    if noise and not args.all:
        head += style(f"   (+{noise} tracking/ad noise hidden — --all to show)",
                      "gray")
    print(f"{label('target:')} {style(summary.get('target') or '(unknown)', 'cyan')}")
    print(head)
    if not findings:
        print("\n" + style("(no findings match the filter)", "gray"))
        return 0
    rows = []
    for f in findings:
        party = {"third_party": "3p", "first_party": "1p"}.get(f.party, "?")
        rows.append([
            sev_label(f.severity), f.category, style(party, "gray"),
            style(f.host or "", "cyan"),
            "" if f.location == "endpoint" else f.location,
            mask_value(f.value_sample),
        ])
    print()
    print(table(rows, ["SEV", "TYPE", "P", "HOST", "LOCATION", "VALUE"]))
    print(style("\n(values masked; --json for full values, --all for "
                "tracking noise)", "gray"))
    return 0
