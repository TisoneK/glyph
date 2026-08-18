"""Config-file format detector (ADR-11).

Extension + multi-feature content analysis (entropy, ASCII ratio, base64
likelihood, ZIP magic). Ported from InjectX ``backend/parser/detector.py``,
adapted to return Glyph's ``Format`` string constants.
"""
from __future__ import annotations

import base64
import json
import math
import zipfile
from collections import Counter
from pathlib import Path
from typing import Tuple

from glyph.vpndec.models import Format

# Extension → format. Multiple extensions map to the same format where apps
# renamed them across versions.
EXTENSION_MAP = {
    ".ehi": Format.EHI, ".hc": Format.HC, ".hat": Format.HAT, ".ha": Format.HAT,
    ".dark": Format.DARK, ".drak": Format.DARK, ".dt": Format.DARK,
    ".darktunnel": Format.DARKTUNNEL, ".tls": Format.TLS,
    ".npv4": Format.NPV, ".inpv": Format.NPV, ".npv": Format.NPV,
    ".nsh": Format.NSH, ".vhd": Format.VHD, ".ziv": Format.ZIV,
    ".ovpn": Format.OVPN, ".conf": Format.CONF, ".lnk": Format.LNK,
}


def _features(raw: bytes) -> Tuple[float, float, float, bool, float, float]:
    """Return (entropy, skew, ascii_ratio, is_zip, base64_likelihood, null_ratio)."""
    sample = raw[:512] if len(raw) >= 512 else raw
    if not sample:
        return (0.0, 0.0, 0.0, False, 0.0, 1.0)
    total = len(sample)
    counts = Counter(sample)
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values() if c)
    skew = 1.0 - (entropy / 8.0)
    ascii_count = sum(1 for b in sample if 32 <= b <= 126 or b in (9, 10, 13))
    ascii_ratio = ascii_count / total
    is_zip = raw[:4] == b"PK\x03\x04"
    b64_chars = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r")
    base64_likelihood = sum(1 for b in sample if b in b64_chars) / total
    null_ratio = sample.count(0) / total
    return (round(entropy, 4), round(skew, 4), round(ascii_ratio, 4),
            is_zip, round(base64_likelihood, 4), round(null_ratio, 4))


def _is_encrypted(raw: bytes) -> bool:
    entropy, skew, ascii_ratio, is_zip, _, null_ratio = _features(raw)
    if is_zip:
        return False
    if entropy > 7.0 and skew < 0.15 and ascii_ratio < 0.4:
        return True
    if entropy > 7.5 and null_ratio < 0.05 and ascii_ratio < 0.5:
        return True
    return False


def detect_format(filepath: str) -> str:
    """Detect a config file's format. Returns a ``Format`` constant."""
    path = Path(filepath)
    ext = path.suffix.lower()
    if ext in EXTENSION_MAP:
        hint = EXTENSION_MAP[ext]
        if _validate(path, hint):
            return hint
    return _detect_by_content(path)


def detect_format_bytes(filename: str, raw: bytes) -> str:
    """Detect format from raw bytes + filename (for in-memory decode)."""
    ext = Path(filename).suffix.lower()
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]
    return _detect_by_content_raw(raw)


def _validate(path: Path, hint: str) -> bool:
    try:
        if hint == Format.EHI:
            if zipfile.is_zipfile(path):
                return True
            raw = path.read_bytes()
            return len(raw) >= 5 and raw[:5] == b"\x00\x03ehi"
        if hint in (Format.HC, Format.HAT, Format.DARK, Format.DARKTUNNEL,
                    Format.TLS, Format.NPV, Format.NSH, Format.VHD, Format.ZIV,
                    Format.LNK):
            return path.exists() and path.stat().st_size > 0
        if hint == Format.OVPN:
            text = path.read_bytes().decode("utf-8", errors="ignore").lower()
            return "client" in text or "dev tun" in text or "remote" in text
    except Exception:
        return False
    return True


def _detect_by_content(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except Exception:
        return Format.UNKNOWN
    return _detect_by_content_raw(raw)


def _detect_by_content_raw(raw: bytes) -> str:
    if not raw:
        return Format.UNKNOWN
    entropy, _, ascii_ratio, is_zip, b64_lik, _ = _features(raw)

    if is_zip:
        return Format.EHI  # default ZIP-based config (EHI legacy is ZIP)

    # Plain JSON?
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return _identify_json(data)
    except Exception:
        pass

    # base64 → JSON?
    if b64_lik > 0.85 and ascii_ratio > 0.85:
        try:
            decoded = base64.b64decode(raw)
            data = json.loads(decoded)
            if isinstance(data, dict):
                return _identify_json(data)
        except Exception:
            pass

    # darktunnel:// envelope?
    try:
        text = raw.decode("utf-8", errors="ignore").strip()
        for pfx in ("darktunnel://", "dark://", "dt://"):
            if text.startswith(pfx):
                return Format.DARK
        if text.startswith("vmess://") or text.startswith("vless://"):
            return Format.NPV
        # OpenVPN?
        low = text.lower()
        if "client" in low and "dev tun" in low:
            return Format.OVPN
    except Exception:
        pass

    if _is_encrypted(raw):
        return Format.ENCRYPTED_UNKNOWN
    return Format.UNKNOWN


def _identify_json(data: dict) -> str:
    keys = {k.lower() for k in data.keys()}
    if len(keys & {"payload", "proxyip", "proxyport", "sshserver", "sshport",
                   "sshuser", "sshpass", "dns", "remotedns"}) >= 2:
        return Format.EHI
    if keys & {"httpcustom", "customheader", "connectiontype", "directconnect",
               "ssl_file"}:
        return Format.HC
    if keys & {"hatunnel", "bughost", "tunneltype", "customsni", "profile",
               "profilev4"}:
        return Format.HAT
    if keys & {"darktunnel", "dark_tunnel", "injecttype", "payloadgenerator",
               "hysteria", "xrayconfig"}:
        return Format.DARK
    if keys & {"tlsvpn", "tls_tunnel", "tlstunnel", "dns_server", "internalip"}:
        return Format.TLS
    if keys & {"napsternetv", "v2ray_config", "vless_config", "vmess_config",
               "ssh_config", "vmess", "outboundbean"}:
        return Format.NPV
    return Format.UNKNOWN
