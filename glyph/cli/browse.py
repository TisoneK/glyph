"""`glyph browse` — helpers for browse mode (ADR-14).

`glyph browse --launch <browser> [--url <url>]` spawns the chosen browser
(Chrome/Edge/Brave — all Chromium) with `--remote-debugging-port=9222` so
`glyph run live --browse <url>` (or `glyph capture live --browse`) can
CDP-attach to it. If the browser is already running on that profile
(profile-lock), it prints the attach instruction instead of failing.

This is UX sugar; the manual path (user launches their own browser with the
flag) is documented in the README and works without this command.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from typing import Optional

from glyph.cli._shared import with_db

# Per-OS default binary names + candidate paths for each browser. `shutil.which`
# handles PATH lookup; the candidate lists cover common install locations that
# aren't on PATH (macOS .app bundles, Windows Program Files).
_BINARIES = {
    "chrome": {
        "darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "linux": ["google-chrome", "google-chrome-stable", "chromium"],
        "win32": [
            os.path.join(os.environ.get("ProgramFiles", ""),
                         "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""),
                         "Google", "Chrome", "Application", "chrome.exe"),
        ],
    },
    "msedge": {
        "darwin": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
        "linux": ["microsoft-edge", "microsoft-edge-stable"],
        "win32": [
            os.path.join(os.environ.get("ProgramFiles(x86)", ""),
                         "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(os.environ.get("ProgramFiles", ""),
                         "Microsoft", "Edge", "Application", "msedge.exe"),
        ],
    },
    "brave": {
        "darwin": ["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"],
        "linux": ["brave-browser", "brave"],
        "win32": [
            os.path.join(os.environ.get("ProgramFiles", ""),
                         "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""),
                         "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        ],
    },
}


def _platform_key() -> str:
    import platform
    s = platform.system().lower()
    if s == "darwin":
        return "darwin"
    if s.startswith("win"):
        return "win32"
    return "linux"


def find_browser(browser: str, browser_path: Optional[str] = None) -> Optional[str]:
    """Resolve a browser binary to launch. Returns an absolute path or None.

    ``browser_path`` (if given) wins. Otherwise: try each candidate for the
    browser + platform — a bare name goes through ``shutil.which`` (PATH
    lookup), an absolute path is checked directly.
    """
    if browser_path:
        return browser_path if os.path.isfile(browser_path) else None
    candidates = _BINARIES.get(browser, {}).get(_platform_key(), [])
    for c in candidates:
        if os.path.isabs(c):
            if os.path.isfile(c):
                return c
        else:
            found = shutil.which(c)
            if found:
                return found
    return None


def add_parser(sub) -> None:
    sp = with_db(sub.add_parser(
        "browse", help="launch a browser for --browse capture, or show attach help"))
    sp.add_argument("--launch", action="store_true",
                    help="spawn the chosen browser with --remote-debugging-port")
    sp.add_argument("--browser", default="chrome",
                    choices=["chrome", "msedge", "brave"],
                    help="browser to launch (default chrome; all Chromium)")
    sp.add_argument("--browser-path", default=None, dest="browser_path",
                    help="explicit path to a browser binary (else auto-detect)")
    sp.add_argument("--url", default=None,
                    help="optional URL to open in the launched browser")
    sp.add_argument("--port", type=int, default=9222,
                    help="remote-debugging-port (default 9222)")
    sp.add_argument("--user-data-dir", default=None, dest="user_data_dir",
                    help="optional Chrome profile dir (default: the browser's "
                         "default profile — your saved logins carry over)")
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    if not args.launch:
        _print_attach_help(args)
        return 0
    binary = find_browser(args.browser, args.browser_path)
    if not binary:
        print(f"error: could not find {args.browser}. Pass --browser-path "
              f"/path/to/{args.browser}, or use --browser chrome|msedge.",
              file=sys.stderr)
        return 1
    cmd = [binary, f"--remote-debugging-port={args.port}"]
    if args.user_data_dir:
        cmd.append(f"--user-data-dir={args.user_data_dir}")
    if args.url:
        cmd.append(args.url)
    print(f"launching {args.browser}: {' '.join(cmd)}", file=sys.stderr)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError as exc:
        print(f"error: failed to launch {binary}: {exc}", file=sys.stderr)
        return 1
    print(f"{args.browser} launched (pid {proc.pid}) on port {args.port}.",
          file=sys.stderr)
    print(f"now run:  glyph run live --browse {args.url or '<url>'} "
          f"--browser {args.browser}", file=sys.stderr)
    print("(the browser must stay open; Ctrl+C in glyph when done capturing.)",
          file=sys.stderr)
    return 0


def _print_attach_help(args: argparse.Namespace) -> None:
    """Without --launch: print the manual one-liner per browser + the attach command."""
    plat = _platform_key()
    print("Browse mode (ADR-14): glyph attaches to YOUR real browser via CDP.\n")
    print("Option A — let glyph launch it:")
    print(f"  glyph browse --launch --browser {args.browser}"
          + (f" --url {args.url}" if args.url else "")
          + f" --port {args.port}\n")
    print("Option B — launch it yourself, then attach:")
    examples = {
        "chrome": {
            "darwin": "open -a 'Google Chrome' --args --remote-debugging-port=9222",
            "linux": "google-chrome --remote-debugging-port=9222 &",
            "win32": 'start chrome --remote-debugging-port=9222',
        },
        "msedge": {
            "darwin": "open -a 'Microsoft Edge' --args --remote-debugging-port=9222",
            "linux": "microsoft-edge --remote-debugging-port=9222 &",
            "win32": 'start msedge --remote-debugging-port=9222',
        },
        "brave": {
            "darwin": "open -a 'Brave Browser' --args --remote-debugging-port=9222",
            "linux": "brave-browser --remote-debugging-port=9222 &",
            "win32": 'start brave --remote-debugging-port=9222',
        },
    }
    print(f"  {examples.get(args.browser, {}).get(plat, '<browser> --remote-debugging-port=9222')}")
    print(f"\nthen:  glyph run live --browse {args.url or '<url>'} "
          f"--browser {args.browser}\n")
    print("Notes:")
    print("  - the browser must be Chromium-based (Chrome/Edge/Brave). "
          "Firefox/Safari: use 'glyph run har' instead.")
    print("  - if the browser is already open on your daily profile, launch a "
          "separate instance with --user-data-dir, or close it first "
          "(profile-lock).")
    print("  - Ctrl+C in glyph DETACHES (your browser + tabs stay open).")
