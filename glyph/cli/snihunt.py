"""`glyph snihunt [target]` — discover SNI bug-host candidates (ADR-10).

Two modes:
  - Direct target: ``glyph snihunt google.com`` — hunt a hostname directly,
    no capture needed. DNS resolve + CT logs + reverse-IP + CDN/zero-rate.
  - Catalog: ``glyph snihunt --db catalog.db`` — re-run over hosts already
    captured in a catalog (the mode `glyph run live` leaves behind).

Discovers NEW candidates — does NOT scrape published bughost lists. Auto-
runs after `sensitive` in `glyph run live`/`run har`; this command is the
standalone entry point.
"""
from __future__ import annotations

import argparse
import sys

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
    sp.add_argument("target", nargs="?", default=None,
                    help="a hostname to hunt directly (e.g. 'google.com'). "
                         "If given, the hunt runs against this target WITHOUT "
                         "needing a capture first — DNS resolve + CT logs + "
                         "reverse-IP + CDN/zero-rate heuristics. If omitted, "
                         "runs over the hosts already in the catalog.")
    sp.add_argument("--target", dest="target_flag", metavar="HOST",
                    help="override the primary capture host (alternative to "
                         "the positional target)")
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
    from glyph.catalog import Flow
    from glyph.snihunt import run_hunt
    # Positional target (glyph snihunt google.com) takes precedence; fall back
    # to --target. Either seeds the hunt directly without a prior capture.
    target = args.target or getattr(args, "target_flag", None)
    cat = catalog(args)
    try:
        if target:
            # Normalize: strip scheme + path, keep just the host.
            t = target.strip()
            for pfx in ("https://", "http://", "www."):
                if t.startswith(pfx):
                    t = t[len(pfx):]
            t = t.split("/")[0].split(":")[0].strip(".")
            if not t:
                print(f"error: invalid target {target!r}", file=sys.stderr)
                return 1
            # Seed the catalog with a synthetic flow so extract_hosts picks the
            # target up. Reuses the full hunt pipeline (CT/reverse-IP/CDN/zero-
            # rate) without a separate code path — no refactor of run_hunt.
            cat.reset()  # fresh hunt — don't mix with a prior capture's hosts
            cat.set_target(t)
            cat.add_flow(Flow(method="GET", url=f"https://{t}/", host="", path="",
                              source="snihunt:seed"))
        # Live progress to stderr so the terminal shows activity (the hunt
        # makes N network calls and looks frozen without it). Suppressed under
        # --json (stdout must stay pure JSON) and when stderr isn't a TTY.
        progress = None
        if not args.json and sys.stderr.isatty():
            def progress(msg: str) -> None:
                print(f"\r  {msg}", end="", file=sys.stderr, flush=True)
        summary = run_hunt(
            cat, target=target,
            net=not args.no_net, probe=args.probe,
            max_domains=args.max_domains,
            progress=progress,
        )
        if progress:
            print(file=sys.stderr)  # newline after the \r progress lines
        findings = [f for f in cat.findings(kind="sni_bug_host")
                    if (f.score or 0) >= args.min_score]
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


def _rows(findings):
    for f in findings:
        yield (f, f.score or 0,
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
    t.add_column("SCR", justify="right")
    t.add_column("SNI HOST", style="cyan", no_wrap=True)
    t.add_column("STATUS", justify="center")
    t.add_column("IP", style="grey58", no_wrap=True)
    t.add_column("CDN", no_wrap=True)
    t.add_column("TYPE")
    t.add_column("SIGNALS", overflow="fold")
    for f, score, cat in _rows(findings):
        from glyph.snihunt import parse_evidence
        ev = parse_evidence(f.evidence or "")
        ip = ev.get("ip", "") or "—"
        cdn = ev.get("cdn", "") or "—"
        # HTTP status from the probe (only populated with --probe).
        status = ev.get("http_status")
        status_str = str(status) if status is not None else "—"
        # Compact signal summary — only what fired, short tokens.
        sigs = []
        if ev.get("captured"):
            sigs.append(f"cap×{ev['captured']}")
        if ev.get("zero_rating"):
            sigs.append("zero:" + ",".join(ev["zero_rating"][:2]))
        if ev.get("wildcard"):
            sigs.append("wildcard")
        if ev.get("shared_cert"):
            sigs.append(f"shared:{ev['shared_cert']}")
        if ev.get("reverse_siblings"):
            sigs.append(f"rip+{ev['reverse_siblings']}")
        if ev.get("reverse_sourced"):
            sigs.append("rip-sourced")
        if ev.get("probe_ok"):
            sigs.append("cert✓")
        sig_str = " ".join(sigs) if sigs else "—"
        t.add_row(C.sev_cell(f.severity), str(score), f.host or "",
                  status_str, ip, cdn, cat, sig_str)
    con.print(t)
    net = "off" if args.no_net else "on"
    probe = "on" if args.probe else "off"
    if not args.probe:
        con.print("[grey58](STATUS shows — because --probe is off. Run with "
                  "--probe to get the HTTP status code + cert for each "
                  "candidate.)[/]")
    con.print(f"[grey58](net {net} · probe {probe} · score ranks how usable "
              "the host is as an SNI — it is NOT a guarantee of free internet)[/]")
    con.print("[grey58](To confirm a host works for free internet, test it "
              "with your tunneling app on your SIM — only a real tunnel test "
              "on the target carrier proves zero-rating.)[/]")


def _render_plain(summary, findings, args) -> None:
    from glyph.snihunt import parse_evidence
    print(f"target: {summary.get('target') or '(unknown)'}")
    print(f"{summary['persisted']} candidate(s) persisted "
          f"({summary['discovered']} discovered): "
          f"{sev_line(summary.get('by_severity', {}))}")
    if not findings:
        print("(no candidates match the filter)")
        return
    if not args.probe:
        print("(STATUS shows — because --probe is off. Run with --probe to "
              "get the HTTP status code + cert for each candidate.)")
    print(f"{'SEV':6} {'SCR':>3}  {'HOST':30} {'STATUS':6} {'IP':16} {'CDN':10} {'TYPE':12} SIGNALS")
    for f, score, cat in _rows(findings):
        ev = parse_evidence(f.evidence or "")
        ip = ev.get("ip", "") or "—"
        cdn = ev.get("cdn", "") or "—"
        status = ev.get("http_status")
        status_str = str(status) if status is not None else "—"
        sigs = []
        if ev.get("captured"): sigs.append(f"cap×{ev['captured']}")
        if ev.get("zero_rating"): sigs.append("zero:" + ",".join(ev["zero_rating"][:2]))
        if ev.get("wildcard"): sigs.append("wildcard")
        if ev.get("shared_cert"): sigs.append(f"shared:{ev['shared_cert']}")
        if ev.get("reverse_siblings"): sigs.append(f"rip+{ev['reverse_siblings']}")
        if ev.get("reverse_sourced"): sigs.append("rip-sourced")
        if ev.get("probe_ok"): sigs.append("cert✓")
        print(f"[{f.severity.upper():6}] {score:>3}  {(f.host or ''):30} "
              f"{status_str:6} {ip:16} {cdn:10} {cat:12} {' '.join(sigs) or '—'}")
    print("(score ranks how usable the host is as an SNI — NOT a guarantee "
          "of free internet. To confirm, test with your tunneling app on "
          "your SIM — only a real tunnel test on the carrier proves it.)")
