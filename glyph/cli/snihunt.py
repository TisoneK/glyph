"""`glyph snihunt` — discover SNI bug-host candidates (ADR-10).

Runs the bounded active-recon stage over the captured catalog: reverse-IP
lookup, certificate-transparency subdomain enumeration, Cloudflare/CDN
frontable-edge detection, zero-rating heuristics, and an optional active
SNI probe. Discovers NEW candidates — does NOT scrape published bughost
lists. Auto-runs after `sensitive` in `glyph run live`/`run har`; this
command re-runs it on an existing catalog.
"""
from __future__ import annotations

import argparse

from glyph.cli import _console as C
from glyph.cli._format import sev_line
from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json

_CAT_LABEL = {
    "sni_zero_rated": "zero-rated",
    "sni_frontable_cdn": "cdn-front",
    "sni_shared_cert": "shared-cert",
    "sni_candidate": "candidate",
}


def add_parser(sub) -> None:
    sp = with_json(with_db(sub.add_parser(
        "snihunt", help="discover SNI bug-host candidates (reverse-IP, CT logs, CDN)")))
    sp.add_argument("--target", metavar="HOST",
                    help="override the primary capture host")
    sp.add_argument("--no-net", action="store_true",
                    help="skip ALL network hunters (local heuristics only — "
                         "extract + embedded CDN ranges + zero-rating patterns)")
    sp.add_argument("--probe", action="store_true",
                    help="enable the active SNI probe (one TLS handshake per "
                         "top candidate, to a public CDN edge). Default OFF.")
    sp.add_argument("--min-score", type=int, default=0, dest="min_score",
                    metavar="N",
                    help="show only candidates scoring >= N (0-100)")
    sp.add_argument("--max-domains", type=int, default=25, dest="max_domains",
                    metavar="N",
                    help="cap on registrable domains to enumerate via CT logs "
                         "(default 25 — each is one network round-trip)")
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.snihunt import run_hunt
    cat = catalog(args)
    try:
        if getattr(args, "target", None):
            cat.set_target(args.target)
        summary = run_hunt(
            cat, target=args.target,
            net=not args.no_net, probe=args.probe,
            max_domains=args.max_domains,
        )
        findings = [f for f in cat.findings(kind="sni_bug_host")
                    if _score(f.evidence) >= args.min_score]
    finally:
        cat.close()

    if args.json:
        emit({"summary": summary,
              "findings": [f.__dict__ for f in findings]}, True)
        return 0

    if C.HAS_RICH:
        _render_rich(summary, findings, args)
    else:
        _render_plain(summary, findings, args)
    return 0


def _score(evidence: str) -> int:
    """Pull the integer score out of an evidence string ('score 72 · ...')."""
    if not evidence:
        return 0
    for tok in evidence.split("·"):
        tok = tok.strip()
        if tok.startswith("score "):
            try:
                return int(tok.split()[1])
            except (ValueError, IndexError):
                return 0
    return 0


def _rows(findings):
    for f in findings:
        yield (f, _score(f.evidence),
               _CAT_LABEL.get(f.category, f.category))


def _render_rich(summary, findings, args) -> None:
    con = C.con()
    target = summary.get("target") or "(unknown)"
    counts = C.sev_counts(summary.get("by_severity", {}))
    title = (f"SNI bug-host candidates  ·  [cyan]{target}[/]  ·  "
             f"[bold]{summary['persisted']}[/] persisted  "
             f"([grey58]{summary['discovered']} discovered[/])  {counts}")
    if summary.get("by_cdn"):
        cdns = " · ".join(f"{v} {k}" for k, v in sorted(summary["by_cdn"].items()))
        title += f"   [grey58]cdn: {cdns}[/]"

    if not findings:
        con.print(title)
        con.print("[grey58](no candidates — try without --min-score, or --no-net off)[/]")
        return

    t = C.table(title=title)
    t.add_column("SEV")
    t.add_column("SCORE", justify="right")
    t.add_column("TYPE")
    t.add_column("SNI HOST", style="cyan", no_wrap=True)
    t.add_column("EVIDENCE", overflow="fold")
    for f, score, cat in _rows(findings):
        t.add_row(C.sev_cell(f.severity), str(score), cat, f.host or "",
                  f.evidence or "")
    con.print(t)
    net = "off" if args.no_net else "on"
    probe = "on" if args.probe else "off"
    con.print(f"[grey58](net {net} · probe {probe} · "
              "candidates are advisory — authorization is yours)[/]")


def _render_plain(summary, findings, args) -> None:
    print(f"target: {summary.get('target') or '(unknown)'}")
    print(f"{summary['persisted']} candidate(s) persisted "
          f"({summary['discovered']} discovered): "
          f"{sev_line(summary.get('by_severity', {}))}")
    if not findings:
        print("(no candidates match the filter)")
        return
    for f, score, cat in _rows(findings):
        print(f"[{f.severity.upper():8}] {score:>3}  {cat:<11} {f.host}  "
              f"— {f.evidence}")
