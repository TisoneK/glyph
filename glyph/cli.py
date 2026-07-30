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


def cmd_run(args: argparse.Namespace) -> int:
    from glyph.capture import ingest_har
    from glyph.schema import infer_all
    from glyph.rosetta import build_dictionary
    cat = _catalog(args)
    try:
        cap = ingest_har(cat, args.file, harvest_html=not args.no_html)
        sch = infer_all(cat)
        ros = build_dictionary(cat)
    finally:
        cat.close()
    print(f"capture:  {cap['flows']} flows, {cap['pages']} page(s)")
    print(f"schema:   {sch['fields']} fields, {sch['enum_candidates']} enum candidate(s)")
    print(f"rosetta:  {ros['entries']} decoded "
          f"({ros['high_confidence']} high-confidence, {ros['needs_review']} to review)")
    print(f"\nCatalog: {args.db}  —  'glyph dict' to view, "
          f"'glyph codegen' to export.")
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

    with_db(sub.add_parser("init", help="create an empty catalog")).set_defaults(
        func=cmd_init)

    sp = with_db(sub.add_parser("capture", help="ingest traffic"))
    csub = sp.add_subparsers(dest="capture_kind", required=True)
    har = with_db(csub.add_parser("har", help="ingest a HAR file"))
    har.add_argument("file")
    har.add_argument("--no-html", action="store_true",
                     help="skip harvesting labels from HTML responses")
    har.set_defaults(func=cmd_capture)

    with_db(sub.add_parser("schema", help="infer fields + enum candidates")
            ).set_defaults(func=cmd_schema)
    with_db(sub.add_parser("rosetta", help="decode codes -> meaning")
            ).set_defaults(func=cmd_rosetta)

    sp = with_json(with_db(sub.add_parser("dict", help="show the dictionary")))
    sp.add_argument("--review", action="store_true",
                    help="only rows needing human review")
    sp.set_defaults(func=cmd_dict)

    with_json(with_db(sub.add_parser("fingerprint", help="backend family"))
              ).set_defaults(func=cmd_fingerprint)
    with_json(with_db(sub.add_parser("auth", help="auth + signing"))
              ).set_defaults(func=cmd_auth)
    with_json(with_db(sub.add_parser("gating", help="rate-limit + bot mgmt"))
              ).set_defaults(func=cmd_gating)

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
    rhar.set_defaults(func=cmd_run)

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
