"""`glyph target list|show|rm` — manage the multi-target catalog (ADR-12).

The catalog is multi-target: a ``targets`` table holds every host ever
captured, and every data row carries a ``target_id``. This command is the
management surface — list registered targets, inspect one, or delete one
(and all its rows) when you're done with it.
"""
from __future__ import annotations

import argparse
import sys

from glyph.cli import _console as C
from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
    sp = with_db(sub.add_parser(
        "target",
        help="list / inspect / remove targets in the multi-target catalog"))
    tsub = sp.add_subparsers(dest="target_kind", required=True)

    # --db is accepted on the parent AND each subcommand so both
    # `glyph --db X target list` and `glyph target list --db X` work.
    lst = with_db(with_json(tsub.add_parser("list", help="list every target (default)")))
    lst.set_defaults(func=run_list)

    show = with_db(with_json(tsub.add_parser("show", help="show one target + its counts")))
    show.add_argument("host_or_id", help="target host (e.g. betika.com) or id")
    show.set_defaults(func=run_show)

    rm = with_db(tsub.add_parser("rm", help="delete a target AND every row that belongs to it"))
    rm.add_argument("host_or_id", help="target host (e.g. betika.com) or id")
    rm.add_argument("--yes", "-y", action="store_true",
                    help="skip the confirmation prompt")
    rm.set_defaults(func=run_rm)

    # Bare `glyph target` defaults to `list`.
    sp.set_defaults(func=run_list, target_kind="list")


def run_list(args: argparse.Namespace) -> int:
    cat = catalog(args)
    try:
        rows = cat.targets()
    finally:
        cat.close()
    if args.json:
        emit(rows, True)
        return 0
    if not rows:
        print("(no targets yet — `glyph run live <url>` or `glyph run har <file>` captures one)")
        return 0
    if C.HAS_RICH:
        _render_rich(rows)
    else:
        _render_plain(rows)
    return 0


def run_show(args: argparse.Namespace) -> int:
    cat = catalog(args)
    try:
        tid = cat.resolve_target(args.host_or_id)
        if tid is None:
            print(f"error: no target matching {args.host_or_id!r}", file=sys.stderr)
            return 1
        info = cat.get_target(tid)
        cat.set_active_target(tid)
        summ = cat.summary()
    finally:
        cat.close()
    if args.json:
        emit({"target": info, "summary": summ}, True)
        return 0
    print(f"target #{info['id']}: {info['host']}")
    if info.get("label"):
        print(f"  label: {info['label']}")
    if info.get("notes"):
        print(f"  notes: {info['notes']}")
    if info.get("created_at"):
        print(f"  created: {info['created_at']}")
    print("  rows:")
    for k in ("endpoints", "flows", "fields", "findings", "dictionary",
              "pages", "vpn_configs"):
        print(f"    {k:<12} {summ.get(k, 0)}")
    return 0


def run_rm(args: argparse.Namespace) -> int:
    cat = catalog(args)
    try:
        tid = cat.resolve_target(args.host_or_id)
        if tid is None:
            print(f"error: no target matching {args.host_or_id!r}", file=sys.stderr)
            return 1
        info = cat.get_target(tid)
        summ = cat.summary(target_id=tid)
        if not args.yes:
            total = sum(summ.get(k, 0) for k in
                        ("endpoints", "flows", "fields", "findings",
                         "dictionary", "pages", "vpn_configs"))
            print(f"About to delete target #{tid} ({info['host']}) "
                  f"and {total} data row(s).")
            ans = input("Type the host to confirm: ").strip().lower()
            if ans != info["host"].lower():
                print("aborted.")
                return 1
        ok = cat.remove_target(tid)
    finally:
        cat.close()
    if not ok:
        print("error: delete failed", file=sys.stderr)
        return 1
    print(f"deleted target #{tid} ({info['host']}) and its data.")
    return 0


def _render_rich(rows) -> None:
    con = C.con()
    t = C.table(title=f"Targets ({len(rows)})")
    t.add_column("ID", justify="right")
    t.add_column("HOST", style="cyan", no_wrap=True)
    t.add_column("FLOWS", justify="right")
    t.add_column("LABEL")
    t.add_column("CREATED", style="grey58")
    for r in rows:
        created = (r.get("created_at") or "")[:10] or "—"
        t.add_row(str(r["id"]), r["host"], str(r.get("flows", 0)),
                  r.get("label") or "—", created)
    con.print(t)
    con.print("[grey58](glyph target show <host> · glyph target rm <host>)[/]")


def _render_plain(rows) -> None:
    print(f"Targets ({len(rows)}):")
    print(f"  {'ID':>3}  {'HOST':30} {'FLOWS':>5}  {'LABEL':12} CREATED")
    for r in rows:
        created = (r.get("created_at") or "")[:10] or "—"
        print(f"  {r['id']:>3}  {r['host']:30} {r.get('flows', 0):>5}  "
              f"{r.get('label') or '—':12} {created}")
    print("(glyph target show <host> · glyph target rm <host>)")
