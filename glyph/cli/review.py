"""`glyph review` — confirm/edit/reject low-confidence decodings."""
from __future__ import annotations

import argparse
import sys

from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
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
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph import review as R
    cat = catalog(args, restore_active=True)
    try:
        if args.stats:
            emit(R.stats(cat), args.json)
            return 0
        if args.auto_confirm is not None:
            n = R.auto_confirm(cat, args.auto_confirm)
            print(f"Auto-confirmed {n} row(s) at confidence >= {args.auto_confirm}")
            return 0
        if args.id is not None:
            if args.reject:
                ok, verb = R.reject(cat, args.id), "rejected"
            elif args.set is not None:
                ok, verb = R.edit(cat, args.id, args.set), "edited"
            else:
                ok, verb = R.confirm(cat, args.id), "confirmed"
            if not ok:
                print(f"error: no dictionary row with id {args.id}", file=sys.stderr)
                return 1
            print(f"Entry {args.id} {verb}.")
            return 0
        R.run_interactive(cat)
        return 0
    finally:
        cat.close()
