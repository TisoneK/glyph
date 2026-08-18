"""Decode entrypoint — detect format, route to the right decryptor (ADR-11).

The single public API: ``decode_file(path)`` or ``decode_bytes(filename, raw)``.
Returns a :class:`VpnConfig`. Handles plain formats (OVPN, CONF, plain JSON)
directly and routes encrypted formats to their decryptor.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from glyph.vpndec import dark, ehi, hc, tls, ziv
from glyph.vpndec.detect import detect_format_bytes
from glyph.vpndec.keys import KeyStore
from glyph.vpndec.models import DecryptStatus, Format, Scheme, VpnConfig


def decode_file(filepath: str, keys: Optional[KeyStore] = None) -> VpnConfig:
    """Detect + decrypt a config file. Returns a :class:`VpnConfig`."""
    path = Path(filepath)
    if not path.exists():
        return VpnConfig(
            filepath=filepath, filename=path.name,
            decryption_status=DecryptStatus.FAILED,
            errors=[f"file not found: {filepath}"],
        )
    raw = path.read_bytes()
    return decode_bytes(path.name, raw, keys=keys, filepath=str(path))


def decode_bytes(filename: str, raw: bytes, keys: Optional[KeyStore] = None,
                 filepath: str = "") -> VpnConfig:
    """Decode raw config bytes + filename. Returns a :class:`VpnConfig`."""
    ks = keys or KeyStore()
    fmt = detect_format_bytes(filename, raw)
    fp = filepath or filename

    if fmt == Format.HC:
        return hc.decrypt_hc(raw, ks, filename, fp)
    if fmt == Format.EHI:
        return ehi.decrypt_ehi(raw, ks, filename, fp)
    if fmt in (Format.DARK, Format.DARKTUNNEL):
        return dark.decrypt_dark(raw, filename, fp)
    if fmt == Format.ZIV:
        return ziv.decrypt_ziv(raw, filename, fp)
    if fmt == Format.TLS:
        return tls.decrypt_tls(raw, ks, filename, fp)

    # Plain formats — no crypto needed.
    if fmt == Format.OVPN or fmt == Format.CONF:
        return _decode_plain(raw, filename, fp, fmt)
    if fmt == Format.UNKNOWN:
        # Last-ditch: maybe it's plain JSON we can identify.
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return _from_plain_json(data, filename, fp)
        except Exception:
            pass

    return VpnConfig(
        filepath=fp, filename=filename, format=fmt,
        decryption_status=DecryptStatus.NO_DECRYPTOR,
        errors=[f"no decryptor for format '{fmt}' "
                f"(HAT/NPV/NSH/VHD are backlog follow-ups)"],
    )


def _decode_plain(raw: bytes, filename: str, filepath: str, fmt: str) -> VpnConfig:
    """Decode a plain-text config (OpenVPN .ovpn, .conf)."""
    try:
        text = raw.decode("utf-8", "ignore")
    except Exception:
        text = ""
    cfg = VpnConfig(
        filepath=filepath, filename=filename, format=fmt,
        is_encrypted=False, decryption_status=DecryptStatus.NOT_ENCRYPTED,
        scheme=Scheme.NONE, confidence=1.0, raw_data={"_text": text},
    )
    # Best-effort: pull `remote <host> <port>` from OpenVPN configs.
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("remote ") and len(line.split()) >= 3:
            parts = line.split()
            cfg.host = parts[1]
            try:
                cfg.port = int(parts[2])
            except (ValueError, IndexError):
                pass
            cfg.protocol = "openvpn"
            break
    return cfg


def _from_plain_json(data: dict, filename: str, filepath: str) -> VpnConfig:
    """A plain (unencrypted) JSON config — wrap it directly."""
    return VpnConfig(
        filepath=filepath, filename=filename, format=Format.UNKNOWN,
        is_encrypted=False, decryption_status=DecryptStatus.NOT_ENCRYPTED,
        scheme=Scheme.NONE, confidence=1.0, raw_data=data,
        host=data.get("host") or data.get("server"),
        port=int(data["port"]) if str(data.get("port", "")).isdigit() else None,
        protocol=(data.get("protocol") or data.get("type") or "").lower() or None,
        sni=data.get("sni"), bug_host=data.get("bugHost"),
        payload=data.get("payload"),
    )
