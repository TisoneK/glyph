"""DARK Tunnel (.dark) envelope decoding — scheme I1 (ADR-11).

A .dark file is ``darktunnel://<base64(JSON)>`` where the JSON is plaintext.
It exposes ``type`` (VLESS/VMESS/TROJAN/SSH/…) and the server/credential
fields — UNLESS the author locked the config, in which case
``encryptedLockedConfig`` holds an opaque blob whose key is not in the file
(device/server-bound). The lock is reported as PARTIAL; the envelope is
still fully decoded.

No crypto needed — this is a base64+JSON envelope. Works without pycryptodome.

Ported from InjectX ``backend/decrypt/dark_decrypt.py``.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from glyph.vpndec import crypto
from glyph.vpndec.models import DecryptStatus, Scheme, VpnConfig

_PREFIXES = ("darktunnel://", "dark://", "dt://")


def decrypt_dark(raw: bytes, filename: str, filepath: str) -> VpnConfig:
    """Decode a DARK Tunnel .dark envelope (scheme I1). No crypto needed."""
    try:
        content = raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError:
        return VpnConfig(
            filepath=filepath, filename=filename, format="dark",
            is_encrypted=True, decryption_status=DecryptStatus.FAILED,
            scheme=Scheme.I1, confidence=0.0,
            errors=["file is not UTF-8 (not a darktunnel:// envelope)"],
        )

    body = content
    for pfx in _PREFIXES:
        if body.startswith(pfx):
            body = body[len(pfx):]
            break

    data: Dict[str, Any] = {}
    decoded = crypto.b64_decode_tolerant(body)
    if decoded is not None:
        try:
            data = json.loads(decoded)
        except (ValueError, TypeError):
            data = {}
    if not data:
        try:
            data = json.loads(content)  # some exports aren't base64-wrapped
        except (ValueError, TypeError):
            return VpnConfig(
                filepath=filepath, filename=filename, format="dark",
                is_encrypted=True, decryption_status=DecryptStatus.FAILED,
                scheme=Scheme.I1, confidence=0.0,
                errors=["envelope is neither base64(JSON) nor plain JSON"],
            )

    if not isinstance(data, dict):
        return VpnConfig(
            filepath=filepath, filename=filename, format="dark",
            is_encrypted=True, decryption_status=DecryptStatus.FAILED,
            scheme=Scheme.I1, confidence=0.0,
            errors=["decoded envelope is not a JSON object"],
        )

    locked = bool(data.get("encryptedLockedConfig"))
    conf = 0.5 if locked else 0.9
    status = DecryptStatus.PARTIAL if locked else DecryptStatus.SUCCESS
    cfg = VpnConfig(
        filepath=filepath, filename=filename, format="dark",
        is_encrypted=True, decryption_status=status, scheme=Scheme.I1,
        confidence=conf, key_label="dark_envelope", raw_data=data,
    )
    if locked:
        cfg.warnings.append("credential body is locked (encryptedLockedConfig) — "
                            "server/creds sealed by the author's DRM")
    _populate_from_dark(cfg, data)
    return cfg


def _populate_from_dark(cfg: VpnConfig, data: Dict[str, Any]) -> None:
    """Lift common fields off a decoded DARK envelope."""
    cfg.protocol = (data.get("type") or data.get("protocol") or "").lower() or None
    cfg.host = data.get("server") or data.get("host") or data.get("address")
    cfg.sni = data.get("sni") or data.get("sniHost") or data.get("peer")
    cfg.bug_host = data.get("bugHost") or data.get("bughost")
    cfg.payload = data.get("payload") or data.get("payloadGenerator")
    port = data.get("port")
    if port:
        try:
            cfg.port = int(port)
        except (ValueError, TypeError):
            pass
    # V2Ray-style nested configs.
    if data.get("v2rayConfig") or data.get("xrayConfig"):
        cfg.protocol = cfg.protocol or "v2ray"
    if data.get("hysteriaConfig"):
        cfg.protocol = cfg.protocol or "hysteria"
    if data.get("shadowsocksConfig"):
        cfg.protocol = cfg.protocol or "shadowsocks"
