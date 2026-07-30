#!/usr/bin/env python3
"""Session 6 — live capture + full-pipeline run against a real target.

Drives headless chromium at the target URL via glyph.capture.driver,
then runs catalog -> schema -> rosetta end-to-end and reports what
Rosetta actually decodes from a REAL target (not synthetic fixtures).

This is the real-world validation the user asked for
(user/preferences.md -> Testing: real-world over green unit tests).

Usage:
    .venv-312/bin/python3 scripts/live_capture_run.py <url> [--out DIR]

Defaults: target = https://linebet.com/en/line/basketball (the betting
site the user captured a HAR from earlier). The user is a legitimate
user of the site; we browse the public line only (no login, no bets).
Per ADR-1: decode-and-document. If bot protection blocks the headless
browser, we report and stop — we do not ship a bypass.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from glyph.catalog import Catalog
from glyph.capture.driver import capture_url
from glyph.schema.infer import infer_all
from glyph.rosetta.dictionary import build_dictionary, collect_candidates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", default="https://linebet.com/en/line/basketball")
    ap.add_argument("--out", default="scripts/capture-out", help="dir to dump artifacts")
    ap.add_argument("--wait", default=None, help="CSS selector to wait for")
    ap.add_argument("--timeout", type=int, default=20000, help="nav timeout ms")
    ap.add_argument("--proxy", default=os.environ.get("LIVE_PROXY"),
                    help="upstream proxy URL (http://user:pass@host:port). "
                         "Defaults to $LIVE_PROXY so creds never land in "
                         "shell history or process listings.")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"=== Glyph live capture + pipeline run ===")
    print(f"target: {args.url}")
    print(f"out:    {out}")
    if args.proxy:
        # Never echo credentials — show only scheme://host:port
        m = re.match(r"([a-z0-9]+://)([^@]+@)?(.+)", args.proxy)
        shown = (m.group(1) + m.group(3)) if m else "(unparseable)"
        print(f"proxy:  {shown}  (credentials hidden)")
    else:
        print(f"proxy:  none (direct egress)")
    print()

    print("[1/4] live capture (headless chromium)...")
    cat = Catalog(path=str(out / "catalog.db"))
    try:
        capture_url(cat, args.url, wait_selector=args.wait,
                    timeout_ms=args.timeout, proxy=args.proxy)
    except Exception as e:
        print(f"  CAPTURE FAILED: {type(e).__name__}: {e}")
        print("  (if this is a bot-protection block, we stop here per ADR-1)")
        traceback.print_exc()
        return 2

    all_flows = cat.all_flows()
    pages = cat.pages()
    print(f"  captured: {len(all_flows)} flows across {len(cat.endpoints())} endpoints")
    print(f"  pages (DOM snapshots): {len(pages)}")
    if pages:
        lab_count = sum(len(p.labels) for p in pages)
        print(f"  DOM labels harvested: {lab_count}")
    print()

    print("[2/4] captured endpoints (top 20 by flow count):")
    eps = sorted(cat.endpoints(), key=lambda e: len(cat.flows_for_endpoint(e.id)), reverse=True)
    for ep in eps[:20]:
        n = len(cat.flows_for_endpoint(ep.id))
        bodies = sum(1 for f in cat.flows_for_endpoint(ep.id) if f.resp_body)
        print(f"  ep#{ep.id}  {n:3d} flows ({bodies} with body)  {ep.method} {ep.path_template[:80]}")
    print()

    print("[3/4] schema inference + enum candidates...")
    try:
        schemas = infer_all(cat)
        enum_cands = cat.enum_candidates()
        print(f"  schemas inferred for {len(schemas)} endpoints")
        print(f"  enum candidates: {len(enum_cands)}")
        for ec in enum_cands[:15]:
            print(f"    {ec.json_path}: {ec.sample_values[:8]}")
    except Exception as e:
        print(f"  SCHEMA FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 3
    print()

    print("[4/4] Rosetta decode (sibling + dom_attr + reference)...")
    try:
        cands = collect_candidates(cat)
        print(f"  raw candidates: {len(cands)} (sibling+dom_attr+reference)")

        counts = build_dictionary(cat)
        print(f"  dictionary: {counts['entries']} entries "
              f"({counts['high_confidence']} high-conf, {counts['needs_review']} need review)")
        dictionary = cat.dictionary()
        print()
        print("  --- top 30 dictionary entries (by confidence) ---")
        for entry in sorted(dictionary, key=lambda d: d.confidence, reverse=True)[:30]:
            rev = " [REVIEW]" if entry.needs_review else ""
            print(f"  conf={entry.confidence:.2f}  {entry.code!r} -> {entry.meaning!r}  "
                  f"[{entry.strategy}]{rev}  {entry.json_path}")
    except Exception as e:
        print(f"  ROSETTA FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 4

    (out / "summary.json").write_text(json.dumps({
        "url": args.url,
        "flow_count": len(all_flows),
        "endpoint_count": len(cat.endpoints()),
        "page_count": len(pages),
        "label_count": sum(len(p.labels) for p in pages),
        "schema_count": len(schemas),
        "enum_candidate_count": len(enum_cands),
        "candidate_count": len(cands),
        "dictionary_count": len(dictionary),
        "dictionary_counts": counts,
    }, indent=2))
    (out / "dictionary.json").write_text(json.dumps(
        [d.__dict__ for d in dictionary], indent=2, default=str))
    print()
    print(f"artifacts written to {out}/ (summary.json, dictionary.json, catalog.db)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
