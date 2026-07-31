"""``glyph`` — the command-line entrypoint over the pipeline stages.

    glyph capture har session.har      # ingest observed traffic
    glyph schema                       # infer fields + flag enum candidates
    glyph rosetta                      # decode codes -> meaning
    glyph run har session.har          # capture -> schema -> rosetta in one go
    glyph dict --review                # show what still needs human confirmation
    glyph codegen --out openapi.json   # emit an OpenAPI 3 spec
    glyph drift before.db after.db     # what changed between two snapshots

Every command that touches a catalog takes ``--db`` (default ``glyph.db``).
Analysis commands take ``--json`` for machine-readable output.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Optional, Sequence

from glyph import __version__


def _catalog(args: argparse.Namespace):
    from glyph.catalog import Catalog
    return Catalog(args.db)


def _emit(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        return
    print(_human(data))


def _human(data: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(data, dict):
        lines = []
        for k, v in data.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:")
                lines.append(_human(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {v}")
        return "\n".join(lines)
    if isinstance(data, list):
        return "\n".join(_human(item, indent) if isinstance(item, (dict, list))
                         else f"{pad}- {item}" for item in data)
    return f"{pad}{data}"


# -- commands -------------------------------------------------------------
def cmd_init(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    cat.close()
    print(f"Initialized catalog at {args.db}")
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    from glyph.capture import ingest_har
    cat = _catalog(args)
    try:
        res = ingest_har(cat, args.file, harvest_html=not args.no_html)
    finally:
        cat.close()
    print(f"Ingested {res['flows']} flows, {res['pages']} page(s) from {args.file}")
    return 0


def _live_kwargs(args: argparse.Namespace) -> dict:
    """Driver options from CLI args, with a GLYPH_PROXY env fallback so the
    proxy (which may carry credentials) need not sit on the command line."""
    return {
        "proxy": args.proxy or os.environ.get("GLYPH_PROXY"),
        "explore": args.explore,
        "settle_ms": args.settle_ms,
        "wait_selector": args.wait_selector,
        "timeout_ms": args.timeout_ms,
    }


def _report_live(url: str, res: dict) -> None:
    print(f"Captured {res['flows']} flows + {res['labels']} DOM labels "
          f"from {url}")
    if res.get("by_source"):
        parts = ", ".join(f"{k.split(':')[-1]}={v}"
                          for k, v in sorted(res["by_source"].items()))
        print(f"  by type: {parts}")
    if res.get("error"):
        print(f"  note: navigation did not fully complete ({res['error']}) — "
              f"captured what loaded before the failure")


def cmd_capture_live(args: argparse.Namespace) -> int:
    from glyph.capture import capture_live
    cat = _catalog(args)
    try:
        res = capture_live(cat, args.url, **_live_kwargs(args))
    finally:
        cat.close()
    _report_live(args.url, res)
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    from glyph.schema import infer_all
    cat = _catalog(args)
    try:
        res = infer_all(cat)
    finally:
        cat.close()
    print(f"Inferred {res['fields']} fields across {res['endpoints']} endpoints; "
          f"{res['enum_candidates']} enum candidate(s)")
    return 0


def cmd_rosetta(args: argparse.Namespace) -> int:
    from glyph.rosetta import build_dictionary
    cat = _catalog(args)
    try:
        res = build_dictionary(cat)
    finally:
        cat.close()
    print(f"Decoded {res['entries']} code(s): {res['high_confidence']} "
          f"high-confidence, {res['needs_review']} need review")
    return 0


def cmd_dict(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    try:
        needs = True if args.review else None
        entries = cat.dictionary(needs_review=needs)
    finally:
        cat.close()
    if args.json:
        _emit([e.__dict__ for e in entries], True)
        return 0
    if not entries:
        print("(dictionary empty — run 'glyph rosetta' first)")
        return 0
    for e in entries:
        flag = " [REVIEW]" if e.needs_review else ""
        print(f"{e.json_path}  {e.code!r} -> {e.meaning!r}  "
              f"(conf {e.confidence}, {e.strategy}){flag}")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from glyph import review as R
    cat = _catalog(args)
    try:
        if args.stats:
            _emit(R.stats(cat), args.json)
            return 0
        if args.auto_confirm is not None:
            n = R.auto_confirm(cat, args.auto_confirm)
            print(f"Auto-confirmed {n} row(s) at confidence >= {args.auto_confirm}")
            return 0
        if args.id is not None:
            if args.reject:
                ok = R.reject(cat, args.id)
                verb = "rejected"
            elif args.set is not None:
                ok = R.edit(cat, args.id, args.set)
                verb = "edited"
            else:  # default single-entry action is confirm
                ok = R.confirm(cat, args.id)
                verb = "confirmed"
            if not ok:
                print(f"error: no dictionary row with id {args.id}", file=sys.stderr)
                return 1
            print(f"Entry {args.id} {verb}.")
            return 0
        # Default: interactive review of pending rows.
        R.run_interactive(cat)
        return 0
    finally:
        cat.close()


def cmd_fingerprint(args: argparse.Namespace) -> int:
    from glyph.fingerprint import fingerprint
    cat = _catalog(args)
    try:
        _emit(fingerprint(cat), args.json)
    finally:
        cat.close()
    return 0


def cmd_auth(args: argparse.Namespace) -> int:
    from glyph.auth import analyze
    cat = _catalog(args)
    try:
        _emit(analyze(cat), args.json)
    finally:
        cat.close()
    return 0


def cmd_gating(args: argparse.Namespace) -> int:
    from glyph.gating import profile
    cat = _catalog(args)
    try:
        _emit(profile(cat), args.json)
    finally:
        cat.close()
    return 0


_KIND_ALIAS = {"data": "sensitive_data", "endpoints": "sensitive_endpoint",
               "risk": "risk"}


def cmd_sensitive(args: argparse.Namespace) -> int:
    from glyph.sensitive import run_scan
    cat = _catalog(args)
    try:
        summary = run_scan(cat)
        kind = _KIND_ALIAS.get(args.kind) if args.kind else None
        findings = cat.findings(kind=kind, min_severity=args.severity)
    finally:
        cat.close()
    if args.json:
        _emit({"summary": summary,
               "findings": [f.__dict__ for f in findings]}, True)
        return 0
    sev = summary.get("by_severity", {})
    sev_line = ", ".join(f"{n} {s}" for s, n in sev.items()) or "none"
    print(f"{summary['total']} finding(s): {sev_line}\n")
    for f in findings:
        val = f"  [value: {f.value_sample}]" if f.value_sample else ""
        loc = f" @ {f.location}" if f.location != "endpoint" else ""
        print(f"[{f.severity.upper():8}] {f.category}{loc}\n"
              f"           {f.evidence}{val}")
    if not findings:
        print("(no findings match the filter)")
    return 0


def cmd_codegen(args: argparse.Namespace) -> int:
    from glyph.codegen import to_openapi_json
    cat = _catalog(args)
    try:
        spec = to_openapi_json(cat)
    finally:
        cat.close()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(spec)
        print(f"Wrote OpenAPI spec to {args.out}")
    else:
        print(spec)
    return 0


def cmd_drift(args: argparse.Namespace) -> int:
    from glyph.drift import diff_catalogs
    report = diff_catalogs(args.before, args.after)
    _emit(report, args.json)
    return 0 if not report["has_drift"] else 2


def cmd_mobile(args: argparse.Namespace) -> int:
    from glyph.mobile import mine_apk, mine_apk_to_catalog
    if args.ingest:
        cat = _catalog(args)
        try:
            res = mine_apk_to_catalog(cat, args.apk)
        finally:
            cat.close()
    else:
        res = mine_apk(args.apk)
    _emit(res, args.json)
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    cat = _catalog(args)
    try:
        summary = cat.summary()
        endpoints = cat.endpoints()
    finally:
        cat.close()
    if args.json:
        _emit({"summary": summary,
               "endpoints": [e.key for e in endpoints]}, True)
        return 0
    print(_human(summary))
    print("endpoints:")
    for e in endpoints:
        note = "" if e.reachability == "direct" else f"  [{e.reachability}]"
        print(f"  {e.key}{note}")
    return 0


def _analyze_and_report(cat, args) -> None:
    """Shared pipeline tail: schema -> rosetta -> (sensitive) + summary.

    Sensitive flagging runs by default (it's passive and operates on data
    already captured); skip with --no-sensitive.
    """
    from glyph.schema import infer_all
    from glyph.rosetta import build_dictionary
    sch = infer_all(cat)
    ros = build_dictionary(cat)
    print(f"schema:    {sch['fields']} fields, {sch['enum_candidates']} enum candidate(s)")
    print(f"rosetta:   {ros['entries']} decoded "
          f"({ros['high_confidence']} high-confidence, {ros['needs_review']} to review)")
    hint = "'glyph dict' to view"
    if not getattr(args, "no_sensitive", False):
        from glyph.sensitive import run_scan
        sens = run_scan(cat)
        sev = sens.get("by_severity", {})
        sev_line = ", ".join(f"{n} {s}" for s, n in sev.items()) or "none"
        print(f"sensitive: {sens['total']} finding(s) ({sev_line})")
        hint += ", 'glyph sensitive' for findings"
    print(f"\nCatalog: {args.db}  —  {hint}, 'glyph codegen' to export.")


def cmd_run(args: argparse.Namespace) -> int:
    from glyph.capture import ingest_har
    cat = _catalog(args)
    try:
        cap = ingest_har(cat, args.file, harvest_html=not args.no_html)
        print(f"capture:   {cap['flows']} flows, {cap['pages']} page(s)")
        _analyze_and_report(cat, args)
    finally:
        cat.close()
    return 0


def cmd_run_live(args: argparse.Namespace) -> int:
    from glyph.capture import capture_live
    cat = _catalog(args)
    try:
        cap = capture_live(cat, args.url, **_live_kwargs(args))
        _report_live(args.url, cap)
        _analyze_and_report(cat, args)
    finally:
        cat.close()
    return 0


# -- parser ---------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="glyph",
        description="Capture, catalog, and decode a target's API surface.")
    p.add_argument("--version", action="version",
                   version=f"glyph {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def with_db(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sp.add_argument("--db", default="glyph.db", help="catalog path")
        return sp

    def with_json(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sp.add_argument("--json", action="store_true", help="JSON output")
        return sp

    def with_live(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Options for the live browser driver — same for `capture live`
        and `run live`. Defaults are tuned to 'just work' on any site."""
        sp.add_argument("url", help="the page to drive and capture")
        sp.add_argument("--proxy", default=None,
                        help="upstream proxy URL (or set GLYPH_PROXY env)")
        sp.add_argument("--explore", type=int, default=2, metavar="N",
                        help="target-agnostic interaction rounds "
                             "(scroll + generic clicks); default 2")
        sp.add_argument("--settle-ms", type=int, default=3000, dest="settle_ms",
                        help="quiet wait after load for late XHR; default 3000")
        sp.add_argument("--wait-selector", default=None, dest="wait_selector",
                        help="optional CSS selector marking 'content settled'")
        sp.add_argument("--timeout-ms", type=int, default=30000, dest="timeout_ms",
                        help="per-step timeout; default 30000")
        return sp

    with_db(sub.add_parser("init", help="create an empty catalog")).set_defaults(
        func=cmd_init)

    sp = with_db(sub.add_parser("capture", help="ingest traffic"))
    csub = sp.add_subparsers(dest="capture_kind", required=True)
    har = with_db(csub.add_parser("har", help="ingest a HAR file"))
    har.add_argument("file")
    har.add_argument("--no-html", action="store_true",
                     help="skip harvesting labels from HTML responses")
    har.set_defaults(func=cmd_capture)
    live = with_live(with_db(csub.add_parser(
        "live", help="drive a live page and capture everything (any site)")))
    live.set_defaults(func=cmd_capture_live)

    with_db(sub.add_parser("schema", help="infer fields + enum candidates")
            ).set_defaults(func=cmd_schema)
    with_db(sub.add_parser("rosetta", help="decode codes -> meaning")
            ).set_defaults(func=cmd_rosetta)

    sp = with_json(with_db(sub.add_parser("dict", help="show the dictionary")))
    sp.add_argument("--review", action="store_true",
                    help="only rows needing human review")
    sp.set_defaults(func=cmd_dict)

    sp = with_json(with_db(sub.add_parser(
        "review", help="confirm/edit/reject low-confidence decodings")))
    sp.add_argument("--stats", action="store_true",
                    help="show review progress and exit")
    sp.add_argument("--auto-confirm", type=float, metavar="THRESHOLD",
                    help="confirm all pending rows at confidence >= THRESHOLD")
    sp.add_argument("--id", type=int, help="act on a single dictionary row")
    sp.add_argument("--reject", action="store_true",
                    help="with --id: reject the mapping")
    sp.add_argument("--set", metavar="MEANING",
                    help="with --id: edit the meaning to MEANING")
    sp.set_defaults(func=cmd_review)

    with_json(with_db(sub.add_parser("fingerprint", help="backend family"))
              ).set_defaults(func=cmd_fingerprint)
    with_json(with_db(sub.add_parser("auth", help="auth + signing"))
              ).set_defaults(func=cmd_auth)
    with_json(with_db(sub.add_parser("gating", help="rate-limit + bot mgmt"))
              ).set_defaults(func=cmd_gating)

    sp = with_json(with_db(sub.add_parser(
        "sensitive", help="flag sensitive data / endpoints / risk indicators")))
    sp.add_argument("--kind", choices=["data", "endpoints", "risk"],
                    help="show only one kind of finding")
    sp.add_argument("--severity", choices=["critical", "high", "medium", "low"],
                    help="show only findings at or above this severity")
    sp.set_defaults(func=cmd_sensitive)

    sp = with_db(sub.add_parser("codegen", help="emit OpenAPI 3"))
    sp.add_argument("--out", help="write spec to this file")
    sp.set_defaults(func=cmd_codegen)

    sp = with_json(sub.add_parser("drift", help="diff two catalogs"))
    sp.add_argument("before")
    sp.add_argument("after")
    sp.set_defaults(func=cmd_drift)

    sp = with_json(with_db(sub.add_parser("mobile", help="mine an APK/IPA")))
    sp.add_argument("apk")
    sp.add_argument("--ingest", action="store_true",
                    help="record discovered URLs as endpoints")
    sp.set_defaults(func=cmd_mobile)

    with_json(with_db(sub.add_parser("catalog", help="summarize the catalog"))
              ).set_defaults(func=cmd_catalog)

    sp = with_db(sub.add_parser("run", help="capture -> schema -> rosetta"))
    rsub = sp.add_subparsers(dest="run_kind", required=True)
    rhar = with_db(rsub.add_parser("har", help="run the pipeline on a HAR file"))
    rhar.add_argument("file")
    rhar.add_argument("--no-html", action="store_true")
    rhar.add_argument("--no-sensitive", action="store_true",
                      help="skip the sensitive/risk scan")
    rhar.set_defaults(func=cmd_run)
    rlive = with_live(with_db(rsub.add_parser(
        "live", help="live-capture a page, then schema + rosetta + sensitive")))
    rlive.add_argument("--no-sensitive", action="store_true",
                       help="skip the sensitive/risk scan")
    rlive.set_defaults(func=cmd_run_live)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
