"""`glyph dict` — show the decoded code -> meaning dictionary."""
from __future__ import annotations

import argparse

from glyph.cli import _console as C
from glyph.cli._format import style
from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json


def add_parser(sub) -> None:
    sp = with_json(with_db(sub.add_parser("dict", help="show the dictionary")))
    sp.add_argument("--review", action="store_true",
                    help="only rows needing human review")
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    cat = catalog(args, restore_active=True)
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
    if C.HAS_RICH:
        _render_rich(entries)
    else:
        _render_plain(entries)
    return 0


def _render_rich(entries) -> None:
    con = C.con()
    t = C.table(title=f"Dictionary  ·  [bold]{len(entries)}[/] decoding(s)")
    t.add_column("PATH", style="cyan", no_wrap=True)
    t.add_column("CODE", justify="right")
    t.add_column("MEANING", style="bold")
    t.add_column("CONF", justify="right")
    t.add_column("STRATEGY", style="grey58")
    t.add_column("", style="yellow")
    for e in entries:
        t.add_row(e.json_path, repr(e.code), str(e.meaning),
                  f"{e.confidence:.2f}", e.strategy,
                  "review" if e.needs_review else "")
    con.print(t)


def _render_plain(entries) -> None:
    for e in entries:
        flag = style(" [REVIEW]", "yellow") if e.needs_review else ""
        print(f"{style(e.json_path, 'cyan')}  {e.code!r} -> "
              f"{style(repr(e.meaning), 'bold')}  "
              f"{style(f'(conf {e.confidence}, {e.strategy})', 'gray')}{flag}")


def _empty_message(review: bool, rosetta_ran, n_flows: int) -> str:
    """Distinguish 'rosetta hasn't run' from 'it ran and found nothing'."""
    if review:
        msg = "(nothing needs review)"
    elif n_flows == 0:
        msg = "(catalog is empty — capture traffic first, e.g. 'glyph run har <file>')"
    elif not rosetta_ran:
        msg = "(no decodings yet — run 'glyph rosetta')"
    else:
        msg = ("(rosetta ran but found no code->meaning correlations in the "
               "captured data)")
    return style(msg, "gray")
