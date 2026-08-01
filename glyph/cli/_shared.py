"""Shared CLI plumbing — catalog opening, common arg groups, live options."""
from __future__ import annotations

import argparse
import os


def catalog(args: argparse.Namespace, *, restore_active: bool = False):
    """Open the catalog. ``restore_active=True`` restores the persisted
    active target (Session 26) so table displays show the CURRENT target's
    rows instead of every target's. Write paths (run/capture) pass the
    default False — they set their own target (ADR-12)."""
    from glyph.catalog import Catalog
    return Catalog(args.db, restore_active=restore_active)


def with_db(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
    sp.add_argument("--db", default="glyph.db", help="catalog path")
    return sp


def with_json(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
    sp.add_argument("--json", action="store_true", help="JSON output")
    return sp


def with_live(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Live browser-driver options — shared by `capture live` and `run live`.

    Defaults are tuned to 'just work' on any site. The target ``url`` is
    OPTIONAL: required for the auto (non-browse) path; optional for
    ``--browse`` (absent = all-traffic capture of every tab)."""
    sp.add_argument("url", nargs="?", default=None,
                    help="the page to drive and capture (optional with --browse: "
                         "absent = capture every tab in the attached browser)")
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
    # --- Browse mode (ADR-14) ---------------------------------------------
    sp.add_argument("--browse", action="store_true",
                    help="browse mode: a VISIBLE browser you drive. Primary = "
                         "CDP-attach to your real browser (Brave/Edge/Chrome) on "
                         "--remote-debugging-port=9222; fallback = launch the "
                         "real-browser binary with a dedicated profile. Captures "
                         "auth/payment/login/deposit/withdrawal flows the auto "
                         "path misses. With a url: target tab + popups only; "
                         "without: every tab (all-traffic). Ctrl+C to stop.")
    sp.add_argument("--cdp-port", type=int, default=9222, dest="cdp_port",
                    help="CDP-attach port (default 9222)")
    sp.add_argument("--cdp-host", default="localhost", dest="cdp_host",
                    help="CDP-attach host (default localhost)")
    sp.add_argument("--browser", default="chrome",
                    choices=["chrome", "msedge", "brave"],
                    help="fallback browser binary to launch (default chrome; "
                         "msedge and brave also work — all Chromium)")
    sp.add_argument("--browser-path", default=None, dest="browser_path",
                    help="explicit path to a browser binary (Brave needs this if "
                         "not auto-detected at the standard locations)")
    sp.add_argument("--incognito", action="store_true",
                    help="launch-fallback only: use a fresh ephemeral context "
                         "(no persistent profile at ~/.glyph/profiles/<host>/)")
    return sp


def live_kwargs(args: argparse.Namespace) -> dict:
    """Driver options from CLI args, with a GLYPH_PROXY env fallback so the
    proxy (which may carry credentials) need not sit on the command line."""
    cdp_url = None
    if getattr(args, "browse", False):
        cdp_url = (os.environ.get("GLYPH_CDP_URL")
                   or f"http://{args.cdp_host}:{args.cdp_port}")
    return {
        "proxy": args.proxy or os.environ.get("GLYPH_PROXY"),
        "explore": args.explore,
        "settle_ms": args.settle_ms,
        "wait_selector": args.wait_selector,
        "timeout_ms": args.timeout_ms,
        "browse": getattr(args, "browse", False),
        "cdp_url": cdp_url,
        "browser": getattr(args, "browser", "chrome"),
        "user_data_dir": None,
        "incognito": getattr(args, "incognito", False),
        "browser_path": getattr(args, "browser_path", None),
    }


def by_type(res: dict) -> dict[str, int]:
    """Aggregate the driver's per-source counters into per-TYPE totals.

    The driver tags response-side flows ``playwright:<resource_type>`` and
    request-side flows ``playwright:request:<resource_type>``. Splitting on
    ``:`` naively would report each type TWICE (once per side) — or, with a
    dict-comprehension, lose one side's count. Summing both sides per type
    gives the real total (e.g. ``document=6`` not ``document=3`` x2).
    """
    types: dict[str, int] = {}
    for k, v in (res.get("by_source") or {}).items():
        t = str(k).split(":")[-1]
        types[t] = types.get(t, 0) + v
    return types


def report_live(url: str, res: dict) -> None:
    print(f"Captured {res['flows']} flows + {res['labels']} DOM labels "
          f"from {url}")
    types = by_type(res)
    if types:
        parts = ", ".join(f"{t}={n}" for t, n in sorted(types.items()))
        print(f"  by type: {parts}")
    if res.get("error"):
        print(f"  note: navigation did not fully complete ({res['error']}) — "
              f"captured what loaded before the failure")
