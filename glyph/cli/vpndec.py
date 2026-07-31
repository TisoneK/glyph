"""`glyph vpndec <file>` — decrypt a VPN config file (ADR-11).

Detects the format, routes to the right decryptor (HC/EHI/DARK/ZIV/TLS),
and persists the decoded config to the catalog's ``vpn_configs`` table.
File-triggered — NOT part of the capture pipeline (unlike snihunt). The
user points it at a file they possess; Glyph decodes it.

Authorization stays with the user (RESEARCH.md §10).
"""
from __future__ import annotations

import argparse

from glyph.cli import _console as C
from glyph.cli._output import emit
from glyph.cli._shared import catalog, with_db, with_json

_STATUS_STYLE = {
    "success": ("green", "✓"),
    "partial": ("yellow", "◐"),
    "not_encrypted": ("cyan", "○"),
    "failed": ("red", "✗"),
    "no_decryptor": ("grey58", "—"),
}


def add_parser(sub) -> None:
    sp = with_json(with_db(sub.add_parser(
        "vpndec", help="decrypt a VPN config file (.hc/.ehi/.dark/.ziv/.tls)")))
    sp.add_argument("file", help="path to the config file to decrypt")
    sp.add_argument("--keyfile", default=None,
                    help="external JSON keyfile (merges over the built-in keys; "
                         "or set GLYPH_VPNKEYFILE env)")
    sp.add_argument("--no-store", action="store_true",
                    help="don't persist the result to the catalog (just print)")
    sp.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from glyph.vpndec import decode_file
    from glyph.vpndec.keys import KeyStore
    import os
    keys = KeyStore(args.keyfile or os.environ.get("GLYPH_VPNKEYFILE"))
    cfg = decode_file(args.file, keys=keys)

    if not args.no_store:
        cat = catalog(args)
        try:
            cat.add_vpn_config(cfg)
        finally:
            cat.close()

    if args.json:
        import dataclasses
        emit(dataclasses.asdict(cfg), True)
        return 0

    if C.HAS_RICH:
        _render_rich(cfg, args)
    else:
        _render_plain(cfg, args)
    return 0


def _render_rich(cfg, args) -> None:
    from rich import box
    from rich.panel import Panel
    from rich.table import Table
    con = C.con()
    style, mark = _STATUS_STYLE.get(cfg.decryption_status, ("grey58", "?"))
    title = (f"VPN config  ·  [cyan]{cfg.filename}[/]  ·  "
             f"[{style}]{mark} {cfg.decryption_status}[/]  "
             f"[grey58]{cfg.format} · {cfg.scheme or '—'} · "
             f"conf {cfg.confidence:.0%}[/]")
    if cfg.key_label:
        title += f"  [grey58]key: {cfg.key_label}[/]"

    g = Table.grid(padding=(0, 2))
    g.add_column(style="bold cyan", justify="left")
    g.add_column()
    if cfg.host:
        g.add_row("host", f"[bold]{cfg.host}[/]" +
                  (f":[bold]{cfg.port}[/]" if cfg.port else ""))
    if cfg.protocol:
        g.add_row("protocol", cfg.protocol)
    if cfg.sni:
        g.add_row("sni", cfg.sni)
    if cfg.bug_host:
        g.add_row("bug host", cfg.bug_host)
    if cfg.ssh_server:
        g.add_row("ssh", f"{cfg.ssh_server}" +
                  (f":{cfg.ssh_port}" if cfg.ssh_port else ""))
    if cfg.ssh_user:
        g.add_row("ssh user", cfg.ssh_user)
    if cfg.ssh_pass:
        g.add_row("ssh pass", "[grey58](redacted in display · kept in catalog)[/]")
    if cfg.proxy_host:
        g.add_row("proxy", f"{cfg.proxy_host}" +
                  (f":{cfg.proxy_port}" if cfg.proxy_port else ""))
    if cfg.payload:
        g.add_row("payload", cfg.payload[:80] + ("…" if len(cfg.payload) > 80 else ""))
    if cfg.dns:
        g.add_row("dns", cfg.dns)
    if cfg.remote_dns:
        g.add_row("remote dns", cfg.remote_dns)
    for w in cfg.warnings:
        g.add_row("", f"[yellow]⚠ {w}[/]")
    for e in cfg.errors:
        g.add_row("", f"[red]✗ {e}[/]")

    con.print(Panel(g, title=title, title_align="left", border_style="cyan",
                    box=box.ROUNDED, padding=(1, 2)))
    stored = "" if args.no_store else "  [grey58](stored in catalog · glyph dashboard → VPN Dec tab)[/]"
    con.print(f"[grey58](authorization is yours — RESEARCH.md §10)[/]{stored}")


def _render_plain(cfg, args) -> None:
    print(f"file: {cfg.filename}")
    print(f"format: {cfg.format}  scheme: {cfg.scheme or '—'}  "
          f"status: {cfg.decryption_status}  conf: {cfg.confidence:.0%}")
    if cfg.host:
        print(f"  host: {cfg.host}" + (f":{cfg.port}" if cfg.port else ""))
    if cfg.protocol:
        print(f"  protocol: {cfg.protocol}")
    if cfg.sni:
        print(f"  sni: {cfg.sni}")
    if cfg.bug_host:
        print(f"  bug host: {cfg.bug_host}")
    if cfg.ssh_server:
        print(f"  ssh: {cfg.ssh_server}" +
              (f":{cfg.ssh_port}" if cfg.ssh_port else ""))
    if cfg.ssh_user:
        print(f"  ssh user: {cfg.ssh_user}")
    if cfg.ssh_pass:
        print(f"  ssh pass: (redacted in display, kept in catalog)")
    if cfg.proxy_host:
        print(f"  proxy: {cfg.proxy_host}" +
              (f":{cfg.proxy_port}" if cfg.proxy_port else ""))
    if cfg.payload:
        print(f"  payload: {cfg.payload[:80]}")
    for w in cfg.warnings:
        print(f"  WARNING: {w}")
    for e in cfg.errors:
        print(f"  ERROR: {e}")
