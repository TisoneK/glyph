"""Shared CLI plumbing — catalog opening, common arg groups, live options."""
from __future__ import annotations

import argparse
import os


def catalog(args: argparse.Namespace):
    from glyph.catalog import Catalog
    return Catalog(args.db)


def with_db(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
    sp.add_argument("--db", default="glyph.db", help="catalog path")
    return sp


def with_json(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
    sp.add_argument("--json", action="store_true", help="JSON output")
    return sp


def with_live(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Live browser-driver options — shared by `capture live` and `run live`.
    Defaults are tuned to 'just work' on any site."""
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


def live_kwargs(args: argparse.Namespace) -> dict:
    """Driver options from CLI args, with a GLYPH_PROXY env fallback so the
    proxy (which may carry credentials) need not sit on the command line."""
    return {
        "proxy": args.proxy or os.environ.get("GLYPH_PROXY"),
        "explore": args.explore,
        "settle_ms": args.settle_ms,
        "wait_selector": args.wait_selector,
        "timeout_ms": args.timeout_ms,
    }


def report_live(url: str, res: dict) -> None:
    print(f"Captured {res['flows']} flows + {res['labels']} DOM labels "
          f"from {url}")
    if res.get("by_source"):
        parts = ", ".join(f"{k.split(':')[-1]}={v}"
                          for k, v in sorted(res["by_source"].items()))
        print(f"  by type: {parts}")
    if res.get("error"):
        print(f"  note: navigation did not fully complete ({res['error']}) — "
              f"captured what loaded before the failure")
