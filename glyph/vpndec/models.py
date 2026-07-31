"""VPN-Config Decoder — data models (ADR-11).

Plain dataclasses (no Pydantic — Glyph's core stays dep-free per ADR-2).
Mirrors InjectX's ``ir/models.py`` NormalizedConfig, adapted to Glyph's
conventions. The ``VpnConfig`` is what every decryptor produces and what
the catalog stores.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class Format:
    """Recognized config file formats (string constants, not an enum, so the
    catalog can store them as plain TEXT without import cycles)."""
    EHI = "ehi"            # HTTP Injector
    HC = "hc"              # HTTP Custom
    HAT = "hat"            # HA Tunnel
    DARK = "dark"          # DARK Tunnel
    DARKTUNNEL = "darktunnel"
    TLS = "tls"            # TLS Tunnel
    NPV = "npv"            # NapsternetV
    NSH = "nsh"            # SocksHTTP
    VHD = "vhd"            # VHD
    ZIV = "ziv"            # ZIVPN
    OVPN = "ovpn"          # OpenVPN (plain text)
    CONF = "conf"          # generic .conf (plain text)
    LNK = "lnk"            # LNK (recognized, no public decryptor)
    ENCRYPTED_UNKNOWN = "encrypted_unknown"
    UNKNOWN = "unknown"


class Scheme:
    """Decryption scheme taxonomy (A=HC, B=EHI, C=NPV, D=NSH, E=HAT, F=TLS,
    G=VHD, H=ZIV, I=DARK). String constants for the same reason as Format."""
    A1 = "A1"; A2 = "A2"; A3 = "A3"; A4 = "A4"; A5 = "A5"   # HTTP Custom
    B1 = "B1"; B2 = "B2"                                     # HTTP Injector
    C1 = "C1"                                                # NapsternetV
    D1 = "D1"                                                # SocksHTTP
    E1 = "E1"                                                # HA Tunnel
    F1 = "F1"                                                # TLS Tunnel
    G1 = "G1"                                                # VHD
    H1 = "H1"                                                # ZIVPN
    I1 = "I1"                                                # DARK Tunnel
    NONE = "none"             # plain text (no decryption needed)
    UNSUPPORTED = "unsupported"


class DecryptStatus:
    SUCCESS = "success"
    PARTIAL = "partial"          # decrypted but some fields stay obfuscated
    FAILED = "failed"            # all keys/schemes tried, none worked
    NOT_ENCRYPTED = "not_encrypted"
    NO_DECRYPTOR = "no_decryptor"  # format known, no public algorithm


@dataclass
class VpnConfig:
    """A decoded VPN config — the canonical IR every decryptor produces.

    Credential fields (ssh_user, ssh_pass) are KEPT (ADR-4 precedent: flag-
    and-keep; the catalog is a sensitive artifact the user owns). The raw
    decrypted JSON/XML is carried in ``raw_data`` for full fidelity.
    """

    filepath: str
    filename: str
    format: str = Format.UNKNOWN
    is_encrypted: bool = False
    decryption_status: str = DecryptStatus.NOT_ENCRYPTED
    scheme: Optional[str] = None
    confidence: float = 0.0
    key_label: str = ""

    # Connection
    host: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None    # ssh / ssl / v2ray / vmess / trojan / ...

    # SSH
    ssh_server: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_user: Optional[str] = None
    ssh_pass: Optional[str] = None

    # Proxy
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None

    # HTTP injection / tunneling
    payload: Optional[str] = None
    sni: Optional[str] = None
    bug_host: Optional[str] = None

    # DNS
    dns: Optional[str] = None
    remote_dns: Optional[str] = None

    # Free-form: the full decrypted structure (for fields not on the IR).
    raw_data: Optional[Dict[str, Any]] = None

    # Audit
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    id: Optional[int] = None
