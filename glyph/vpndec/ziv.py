"""ZIVPN (.ziv) decryption — scheme H1 (ADR-11).

AES-256-GCM with PBKDF2-HMAC-SHA256 key derivation.
File format: "salt.iv.ciphertext_mac" (3 dot-separated base64 segments).
Key derivation: PBKDF2(password, salt, SHA256, 1000 iters) → 32-byte AES key.
Decrypted output: XML ``<entry key="...">value</entry>`` pairs.

The password is a hardcoded app constant (extracted from the ZIVPN APK's
class o3.a — five base64 parts concatenating to "SecurePart1..SecurePart5").
Older builds used 'fubvx788b46v' (X-Tools era).

Ported from InjectX ``backend/decrypt/ziv_decrypt.py``.
"""
from __future__ import annotations

import re
from typing import Dict

from glyph.vpndec import crypto
from glyph.vpndec.models import DecryptStatus, Scheme, VpnConfig

# Known ZIVPN passwords — try all. Current build's key is extracted from the
# APK (com.zi.zivpn, class o3.a); the legacy ones are from X-Tools.
_ZIV_PASSWORDS = [
    b"SecurePart1SecurePart2SecurePart3SecurePart4SecurePart5",
    b"fubvx788b46v",
    b"fubvx788B4mev",
    b"zivpn",
    b"ZIVPN",
    b"com.zi.zivpn",
    b"zi.zivpn",
]

_FIELD_MAP = {
    "sshServer": "ssh_server", "sshPort": "ssh_port", "sshUser": "ssh_user",
    "sshPass": "ssh_pass", "proxyHost": "proxy_host", "proxyPort": "proxy_port",
    "sni": "sni", "bugHost": "bug_host", "payload": "payload",
    "dnsServer": "dns", "remoteDns": "remote_dns", "notes": "notes",
    "udpserver": "host", "udpResolver": "remote_dns", "sniHost": "sni",
}


def decrypt_ziv(raw: bytes, filename: str, filepath: str) -> VpnConfig:
    """Decrypt a ZIVPN .ziv config (scheme H1)."""
    if not crypto.HAS_CRYPTO:
        return VpnConfig(
            filepath=filepath, filename=filename, format="ziv",
            is_encrypted=True, decryption_status=DecryptStatus.NO_DECRYPTOR,
            scheme=Scheme.H1, confidence=0.0,
            errors=["pycryptodome not installed (pip install 'glyph-re[crypto]')"],
        )

    try:
        content = raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError:
        return VpnConfig(
            filepath=filepath, filename=filename, format="ziv",
            is_encrypted=True, decryption_status=DecryptStatus.FAILED,
            scheme=Scheme.H1, confidence=0.0,
            errors=["file is not valid UTF-8"],
        )

    parts = content.split(".")
    if len(parts) != 3:
        return VpnConfig(
            filepath=filepath, filename=filename, format="ziv",
            is_encrypted=True, decryption_status=DecryptStatus.FAILED,
            scheme=Scheme.H1, confidence=0.0,
            errors=[f"expected 3 dot-separated parts, got {len(parts)}"],
        )

    try:
        import base64
        salt = base64.b64decode(parts[0])
        nonce = base64.b64decode(parts[1])
        ct_mac = base64.b64decode(parts[2])
    except Exception as exc:
        return VpnConfig(
            filepath=filepath, filename=filename, format="ziv",
            is_encrypted=True, decryption_status=DecryptStatus.FAILED,
            scheme=Scheme.H1, confidence=0.0,
            errors=[f"base64 decode failed: {exc}"],
        )

    for pw in _ZIV_PASSWORDS:
        key = crypto.pbkdf2_sha256(pw, salt, dkLen=32, count=1000)
        if key is None:
            continue
        dec = crypto.aes_gcm_decrypt(ct_mac[:-16], key, nonce, ct_mac[-16:])
        if dec is None:
            continue
        try:
            text = dec.decode("utf-8", "ignore")
        except Exception:
            continue
        normalized = _parse_ziv_xml(text)
        cfg = VpnConfig(
            filepath=filepath, filename=filename, format="ziv",
            is_encrypted=True, decryption_status=DecryptStatus.SUCCESS,
            scheme=Scheme.H1, confidence=0.9,
            key_label=f"ziv:{pw.decode()}", raw_data=normalized,
        )
        _populate_from_ziv(cfg, normalized)
        return cfg

    return VpnConfig(
        filepath=filepath, filename=filename, format="ziv",
        is_encrypted=True, decryption_status=DecryptStatus.FAILED,
        scheme=Scheme.H1, confidence=0.0,
        errors=["all known ZIVPN passwords failed (MAC check) — key may have rotated"],
    )


def _parse_ziv_xml(text: str) -> Dict:
    """Parse ZIVPN XML ``<entry key="...">value</entry>`` pairs into a dict."""
    raw = dict(re.findall(r'<entry key="([^"]*)">([^<]*)</entry>', text))
    out: Dict = {}
    for ziv_key, ir_key in _FIELD_MAP.items():
        if ziv_key in raw:
            out[ir_key] = raw[ziv_key]
    if "ssh_server" in out and isinstance(out["ssh_server"], str):
        ssh = out["ssh_server"]
        if ":" in ssh:
            h, _, p = ssh.partition(":")
            out.setdefault("host", h)
            try:
                out.setdefault("port", int(p))
            except ValueError:
                pass
        else:
            out.setdefault("host", ssh)
    if "ssh_server" in out:
        out["protocol"] = "ssh"
    out["_all_fields"] = raw
    return out


def _populate_from_ziv(cfg: VpnConfig, data: Dict) -> None:
    cfg.host = data.get("host")
    cfg.port = data.get("port")
    cfg.protocol = data.get("protocol")
    cfg.ssh_server = data.get("ssh_server")
    cfg.ssh_port = data.get("ssh_port")
    cfg.ssh_user = data.get("ssh_user")
    cfg.ssh_pass = data.get("ssh_pass")
    cfg.proxy_host = data.get("proxy_host")
    cfg.proxy_port = data.get("proxy_port")
    cfg.sni = data.get("sni")
    cfg.bug_host = data.get("bug_host")
    cfg.payload = data.get("payload")
    cfg.dns = data.get("dns")
    cfg.remote_dns = data.get("remote_dns")
