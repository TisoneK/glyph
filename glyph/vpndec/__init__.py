"""VPN-Config Decoder — decrypt VPN tunnel config files (ADR-11).

Borrows algorithms from InjectX (https://github.com/TisoneK/InjectX), which
itself ports the public Pancho7532/HCDecryptor + HCTools/hcdecryptor research.
Glyph does NOT import or depend on InjectX — the algorithms are ported into
Glyph's conventions (dataclasses, stdlib core, optional pycryptodome).

File-triggered: ``glyph vpndec <file>`` decrypts a config the user supplies
(.hc / .ehi / .dark / .ziv / .tls / .hat / .npv / .nsh / .vhd / .ovpn) and
persists the normalized result to the catalog's ``vpn_configs`` table.

    from glyph.vpndec import decode_file
    cfg = decode_file("myconfig.hc")   # → VpnConfig
    print(cfg.host, cfg.port, cfg.protocol, cfg.sni)

Authorization stays with the user (RESEARCH.md §10); Glyph decodes configs
the user already possesses and names no tunneling tool (ADR-3).
"""
from __future__ import annotations

from glyph.vpndec.decode import decode_file, decode_bytes
from glyph.vpndec.models import VpnConfig, Format, Scheme, DecryptStatus

__all__ = ["decode_file", "decode_bytes", "VpnConfig", "Format", "Scheme",
           "DecryptStatus"]
