"""`glyph dict` — show the decoded code -> meaning dictionary."""
from __future__ import annotations

import argparse

from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
    sp = with_json(with_db(sub.add_parser("dict", help="show the dictionary")))
    sp.add_argument("--review", action="store_true",
                    help="only rows needing human review")
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    cat = catalog(args)
    try:
        needs = True if args.review else None
        entries = cat.dictionary(needs_review=needs)
        ran = cat.get_meta("rosetta_ran")
        n_flows = cat.summary()["flows"]
    finally:
        cat.close()

    if args.json:
        emit([e.__dict__ for e in entries], True)
        return 0
    if not entries:
        print(_empty_message(args.review, ran, n_flows))
        return 0
    for e in entries:
        flag = " [REVIEW]" if e.needs_review else ""
        print(f"{e.json_path}  {e.code!r} -> {e.meaning!r}  "
              f"(conf {e.confidence}, {e.strategy}){flag}")
    return 0


def _empty_message(review: bool, rosetta_ran, n_flows: int) -> str:
    """Distinguish 'rosetta hasn't run' from 'it ran and found nothing'."""
    if review:
        return "(nothing needs review)"
    if n_flows == 0:
        return "(catalog is empty — capture traffic first, e.g. 'glyph run har <file>')"
    if not rosetta_ran:
        return "(no decodings yet — run 'glyph rosetta')"
    return ("(rosetta ran but found no code->meaning correlations in the "
            "captured data)")
