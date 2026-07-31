"""TLS Tunnel (.tls) decryption — scheme F1 (ADR-11).

AES-256-GCM with a single hardcoded key.
File format: "<build_number>:<base64_payload>" (legacy) or
             "<base64>:::::" (newer, no build number, trailing colons) or
             pure base64 (newest, no colon).
base64_payload decodes to: IV(12 bytes) + ciphertext + MAC(16 bytes).
Decrypted data is colon-separated with base64-encoded subfields.

Ported from InjectX ``backend/decrypt/tls_decrypt.py``.
Algorithms credit: Pancho7532/HCDecryptor tlsDecryptor.lib.js.
"""
from __future__ import annotations

import base64
from typing import Dict, Optional

from glyph.vpndec import crypto
from glyph.vpndec.keys import KeyStore
from glyph.vpndec.models import DecryptStatus, Scheme, VpnConfig

_CONN_METHODS = ["Default", "Payload", "SNI", "Payload+SNI", "Payload+Proxy",
                 "Payload+Proxy+SNI", "DNS Tunnel"]
_DNS_TYPES = ["UDP[53]", "DoT[853]", "DoH[853]"]
_PORTS = ["Auto", "25", "80", "110", "143", "443", "465", "853", "993", "995",
          "2525", "3128", "8080", "8888", "33827"]


def _b64_text(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    try:
        return base64.b64decode(val).decode("utf-8", "replace")
    except Exception:
        return val


def _parse_fields(text: str, build_number: int) -> Dict:
    parts = text.split(":")
    out: Dict = {}
    if build_number >= 200 and len(parts) >= 14:
        try:
            out["connection_method"] = _CONN_METHODS[int(parts[0])]
        except (ValueError, IndexError):
            out["connection_method_raw"] = parts[0]
        out["payload"] = _b64_text(parts[1]) if len(parts) > 1 else None
        out["sni"] = _b64_text(parts[2]) if len(parts) > 2 else None
        out["note"] = _b64_text(parts[3]) if len(parts) > 3 else None
        out["ssh_server"] = _b64_text(parts[4]) if len(parts) > 4 else None
        if len(parts) > 5:
            try:
                out["predefined_port"] = _PORTS[int(parts[5])]
            except (ValueError, IndexError):
                out["predefined_port_raw"] = parts[5]
        out["ssh_port"] = _b64_text(parts[6]) if len(parts) > 6 else None
        out["ssh_user"] = _b64_text(parts[7]) if len(parts) > 7 else None
        out["ssh_pass"] = _b64_text(parts[8]) if len(parts) > 8 else None
        out["proxy_url"] = _b64_text(parts[9]) if len(parts) > 9 else None
        out["proxy_port"] = _b64_text(parts[10]) if len(parts) > 10 else None
        if len(parts) > 11:
            try:
                out["dns_type"] = _DNS_TYPES[int(parts[11])]
            except (ValueError, IndexError):
                out["dns_type_raw"] = parts[11]
        out["dns_server"] = _b64_text(parts[12]) if len(parts) > 12 else None
        out["dns_domain"] = _b64_text(parts[13]) if len(parts) > 13 else None
        out["dns_public_key"] = _b64_text(parts[14]) if len(parts) > 14 else None
    else:
        out["_raw_decrypted"] = text
    return out


def _score(data: Dict) -> float:
    if not data:
        return 0.0
    score = 0.3  # GCM auth tag passed
    if data.get("connection_method"):
        score += 0.15
    if data.get("ssh_server"):
        score += 0.2
    if data.get("sni"):
        score += 0.1
    if data.get("payload"):
        score += 0.1
    if data.get("ssh_user"):
        score += 0.1
    if data.get("proxy_url"):
        score += 0.05
    return min(1.0, score)


def decrypt_tls(raw: bytes, keys: KeyStore, filename: str,
                filepath: str) -> VpnConfig:
    """Decrypt a TLS Tunnel .tls config (scheme F1)."""
    tls_keys = keys.tls
    if not crypto.HAS_CRYPTO or not tls_keys:
        return VpnConfig(
            filepath=filepath, filename=filename, format="tls",
            is_encrypted=True,
            decryption_status=DecryptStatus.NO_DECRYPTOR if not crypto.HAS_CRYPTO
            else DecryptStatus.FAILED,
            scheme=Scheme.F1, confidence=0.0,
            errors=["pycryptodome not installed (pip install 'glyph-re[crypto]')"
                    if not crypto.HAS_CRYPTO else "no tls keys available"],
        )

    try:
        content = raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError:
        return VpnConfig(
            filepath=filepath, filename=filename, format="tls",
            is_encrypted=True, decryption_status=DecryptStatus.FAILED,
            scheme=Scheme.F1, confidence=0.0,
            errors=["file is not valid UTF-8"],
        )

    build_number = 0
    b64_payload = content
    if ":" in content:
        prefix = content[:content.index(":")]
        try:
            build_number = int(prefix)
            b64_payload = content[content.index(":") + 1:]
        except ValueError:
            b64_payload = content.rstrip(":")
    b64_payload = b64_payload.strip().rstrip(":").strip()
    # Re-pad (newer builds strip '=' padding).
    pad = (-len(b64_payload)) % 4
    if pad:
        b64_payload += "=" * pad

    try:
        payload_bytes = base64.b64decode(b64_payload)
    except Exception:
        return VpnConfig(
            filepath=filepath, filename=filename, format="tls",
            is_encrypted=True, decryption_status=DecryptStatus.FAILED,
            scheme=Scheme.F1, confidence=0.0,
            errors=["base64 payload decode failed"],
        )

    if len(payload_bytes) < 28:  # 12 IV + 16 MAC minimum
        return VpnConfig(
            filepath=filepath, filename=filename, format="tls",
            is_encrypted=True, decryption_status=DecryptStatus.FAILED,
            scheme=Scheme.F1, confidence=0.0,
            errors=[f"payload too short ({len(payload_bytes)} bytes)"],
        )

    iv = payload_bytes[:12]
    tag = payload_bytes[-16:]
    ct = payload_bytes[12:-16]

    for key_b64 in tls_keys:
        key = crypto.b64_decode_tolerant(key_b64)
        if key is None or len(key) != 32:
            continue
        dec = crypto.aes_gcm_decrypt(ct, key, iv, tag)
        if dec is None:
            continue
        try:
            text = dec.decode("utf-8", "strict")
        except Exception:
            continue
        data = _parse_fields(text, build_number)
        conf = _score(data)
        status = DecryptStatus.SUCCESS if conf >= 0.5 else DecryptStatus.PARTIAL
        cfg = VpnConfig(
            filepath=filepath, filename=filename, format="tls",
            is_encrypted=True, decryption_status=status, scheme=Scheme.F1,
            confidence=conf, key_label=key_b64[:20] + "…", raw_data=data,
        )
        _populate_from_tls(cfg, data)
        return cfg

    return VpnConfig(
        filepath=filepath, filename=filename, format="tls",
        is_encrypted=True, decryption_status=DecryptStatus.FAILED,
        scheme=Scheme.F1, confidence=0.0,
        errors=["all tls keys failed (GCM MAC check) — key may have rotated"],
    )


def _populate_from_tls(cfg: VpnConfig, data: Dict) -> None:
    cfg.ssh_server = data.get("ssh_server")
    cfg.ssh_user = data.get("ssh_user")
    cfg.ssh_pass = data.get("ssh_pass")
    cfg.sni = data.get("sni")
    cfg.payload = data.get("payload")
    cfg.proxy_host = data.get("proxy_url")
    cfg.proxy_port = int(data["proxy_port"]) if data.get("proxy_port") and \
        str(data["proxy_port"]).isdigit() else None
    cfg.dns = data.get("dns_server")
    cfg.remote_dns = data.get("dns_domain")
    if cfg.ssh_server:
        cfg.host = cfg.ssh_server
        cfg.protocol = "ssh"
    if data.get("ssh_port") and str(data["ssh_port"]).isdigit():
        cfg.ssh_port = int(data["ssh_port"])
        cfg.port = cfg.ssh_port
    if data.get("connection_method"):
        cm = data["connection_method"]
        if "SNI" in cm and not cfg.sni:
            cfg.warnings.append("SNI connection method but no SNI field parsed")
