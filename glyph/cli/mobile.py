"""`glyph mobile` — mine endpoints/URLs from an app package."""
from __future__ import annotations

import argparse

from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
    sp = with_json(with_db(sub.add_parser("mobile", help="mine an APK/IPA")))
    sp.add_argument("apk")
    sp.add_argument("--ingest", action="store_true",
                    help="record discovered URLs as endpoints")
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.mobile import mine_apk, mine_apk_to_catalog
    if args.ingest:
        cat = catalog(args, restore_active=True)
        try:
            res = mine_apk_to_catalog(cat, args.apk)
        finally:
            cat.close()
    else:
        res = mine_apk(args.apk)
    emit(res, args.json)
    return 0
