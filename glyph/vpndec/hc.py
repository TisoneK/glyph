"""HTTP Custom (.hc) decryption — schemes A1-A4 (ADR-11).

A1: XOR deobfuscation + AES-128-ECB (SHA1 key derivation, ePro keys)
A2: Raw AES-128-ECB (no XOR, SHA1 key derivation)
A3: HC v233 double-encryption (XOR + plain key layer + SHA1 key layer)
A4: eProxy raw AES-128-ECB (pisahConk delimiter)

Ported from InjectX ``backend/decrypt/hc_decrypt.py`` (same algorithms,
same keys) — adapted to Glyph's centralized ``crypto`` module.
Algorithms credit: Pancho7532/HCDecryptor, HCTools/hcdecryptor.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from glyph.vpndec import crypto
from glyph.vpndec.keys import KeyStore
from glyph.vpndec.models import DecryptStatus, Scheme, VpnConfig

# Unicode XOR cycling key (Pancho7532).
_XOR_VALUES = [0x3002, 0x3003, 0x3004, 0x3005, 0x3006, 0x3007,
               0x3008, 0x3009, 0x300A, 0x300B, 0x300C, 0x300D,
               0x300E, 0x300F, 0x3010, 0x3011, 0x3012, 0x3013,
               0x3014, 0x3015]
_SPLIT_CONFIG = "[splitConfig]"
_PISAH_CONK = "[pisahConk]"

_KNOWN_HC_FIELDS = {"payload", "proxyURL", "sshAddr", "sniValue", "bugHost",
                    "connectionType", "tunnelType", "dns", "remoteDns",
                    "sshServer", "sshPort", "sshUser", "sshPassword",
                    "proxyHost", "proxyPort", "customPayload", "sslFile",
                    "directConnect", "blockRooted", "expireDate"}


def _xor_deobfuscate(data: bytes) -> bytes:
    """Strip Unicode spacing/newlines, then XOR with the cycling key."""
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return b""
    cleaned = [ch for ch in text
               if not (0x2000 <= ord(ch) <= 0x20EF or ch in ("\n", "\r"))]
    out = []
    b = 0
    for ch in cleaned:
        out.append(chr(ord(ch) ^ _XOR_VALUES[b]))
        b = (b + 1) % len(_XOR_VALUES)
    return "".join(out).encode("utf-8")


def _try_aes_b64(raw: bytes, key: bytes) -> Optional[Dict[str, Any]]:
    """AES-ECB decrypt a base64 blob, parse as JSON or delimited text."""
    ct = crypto.b64_decode_tolerant(raw.decode("utf-8", "ignore")) if raw else None
    if ct is None:
        return None
    decrypted = crypto.aes_ecb_decrypt(ct, key)
    if decrypted is None:
        return None
    try:
        text = decrypted.decode("utf-8", "strict")
    except Exception:
        return None
    if _SPLIT_CONFIG in text or _PISAH_CONK in text:
        delim = _SPLIT_CONFIG if _SPLIT_CONFIG in text else _PISAH_CONK
        return {"_raw_delimited": text, "_delimiter": delim}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _score(data: Dict[str, Any]) -> float:
    if not data:
        return 0.0
    raw = data.get("_raw_delimited", "")
    if raw:
        delim = data.get("_delimiter", _SPLIT_CONFIG)
        n = len([p for p in raw.split(delim) if p.strip()])
        return min(1.0, n / 10.0) if n >= 3 else 0.2
    overlap = len(set(data.keys()) & _KNOWN_HC_FIELDS)
    if overlap >= 5:
        return 0.95
    if overlap >= 3:
        return 0.8
    if overlap >= 1:
        return 0.5
    return 0.2


def decrypt_hc(raw: bytes, keys: KeyStore, filename: str,
               filepath: str) -> VpnConfig:
    """Try all HC schemes (A1-A4) and return the best-confidence result."""
    epro = keys.epro
    best: Optional[tuple] = None  # (scheme, confidence, data, key_label)

    # A1: XOR + AES-128-ECB (SHA1 keys)
    xored = _xor_deobfuscate(raw)
    if xored:
        for pw in epro[0]:
            res = _try_aes_b64(xored, crypto.sha1_key16(pw))
            if res:
                c = _score(res)
                if best is None or c > best[1]:
                    best = (Scheme.A1, c, res, pw)
                    if c >= 0.8:
                        break

    # A2: raw AES-128-ECB (no XOR)
    for pw in epro[0]:
        res = _try_aes_b64(raw, crypto.sha1_key16(pw))
        if res:
            c = _score(res)
            if best is None or c > best[1]:
                best = (Scheme.A2, c, res, pw)
                if c >= 0.8:
                    break

    # A3: v233 double-encryption (XOR + plain key, then SHA1 key)
    if xored:
        for v233 in epro[1]:
            plain_key = v233.encode("utf-8")[:16]
            layer1 = crypto.aes_ecb_decrypt(
                crypto.b64_decode_tolerant(xored.decode("utf-8", "ignore")) or b"",
                plain_key) if xored else None
            if layer1 is None:
                continue
            for pw in epro[0]:
                res = _try_aes_b64(layer1, crypto.sha1_key16(pw))
                if res:
                    c = _score(res)
                    if best is None or c >= 0.5 and c > best[1]:
                        best = (Scheme.A3, c, res, f"{v233}+{pw}")
                        if c >= 0.5:
                            break
            if best and best[0] == Scheme.A3 and best[1] >= 0.5:
                break

    # A4: eProxy raw AES-128-ECB (pisahConk delimiter)
    for pw in epro[0]:
        ct = crypto.b64_decode_tolerant(raw.decode("utf-8", "ignore"))
        if ct is None:
            continue
        dec = crypto.aes_ecb_decrypt(ct, crypto.sha1_key16(pw))
        if dec:
            try:
                text = dec.decode("utf-8", "strict")
                if _PISAH_CONK in text:
                    n = len([p for p in text.split(_PISAH_CONK) if p.strip()])
                    c = min(1.0, n / 15.0) if n >= 5 else 0.3
                    res = {"_raw_delimited": text, "_delimiter": _PISAH_CONK}
                    if best is None or c > best[1]:
                        best = (Scheme.A4, c, res, pw)
                        if c >= 0.8:
                            break
            except Exception:
                pass

    if best is None:
        return VpnConfig(
            filepath=filepath, filename=filename, format="hc",
            is_encrypted=True, decryption_status=DecryptStatus.FAILED,
            scheme=Scheme.A1, confidence=0.0,
            errors=["all HC schemes (A1-A4) failed — key may have rotated"],
        )
    scheme, conf, data, key_label = best
    status = (DecryptStatus.SUCCESS if conf >= 0.5
              else DecryptStatus.PARTIAL)
    cfg = VpnConfig(
        filepath=filepath, filename=filename, format="hc",
        is_encrypted=True, decryption_status=status, scheme=scheme,
        confidence=conf, key_label=key_label, raw_data=data,
    )
    _populate_from_hc(cfg, data)
    return cfg


def _populate_from_hc(cfg: VpnConfig, data: Dict[str, Any]) -> None:
    """Lift the common fields off a decrypted HC dict onto the VpnConfig IR."""
    if not data:
        return
    # Delimited format — parse [splitConfig] / [pisahConk] parts by position.
    raw = data.get("_raw_delimited")
    if raw:
        delim = data.get("_delimiter", _SPLIT_CONFIG)
        parts = [p.strip() for p in raw.split(delim) if p.strip()]
        # HC delimited layout (positional, best-effort — varies by version):
        # [0]=payload, [1]=proxyURL, [2]=sshAddr, [3]=sniValue, [4]=bugHost...
        if len(parts) > 0:
            cfg.payload = parts[0] or None
        if len(parts) > 1 and ":" in parts[1]:
            cfg.proxy_host, _, port = parts[1].partition(":")
            cfg.proxy_port = int(port) if port.isdigit() else None
        if len(parts) > 2 and ":" in parts[2]:
            cfg.ssh_server, _, port = parts[2].partition(":")
            cfg.ssh_port = int(port) if port.isdigit() else None
            cfg.host = cfg.ssh_server
            cfg.port = cfg.ssh_port
            cfg.protocol = "ssh"
        if len(parts) > 3:
            cfg.sni = parts[3] or None
        if len(parts) > 4:
            cfg.bug_host = parts[4] or None
        return
    # JSON format — pull known fields directly.
    cfg.payload = data.get("payload") or data.get("customPayload")
    cfg.sni = data.get("sniValue") or data.get("sni")
    cfg.bug_host = data.get("bugHost")
    cfg.dns = data.get("dns")
    cfg.remote_dns = data.get("remoteDns")
    ssh = data.get("sshServer") or data.get("sshAddr")
    if ssh:
        cfg.ssh_server = ssh
        cfg.host = ssh
        cfg.protocol = "ssh"
    if data.get("sshPort"):
        try:
            cfg.ssh_port = int(data["sshPort"])
            cfg.port = cfg.ssh_port
        except (ValueError, TypeError):
            pass
    cfg.ssh_user = data.get("sshUser")
    cfg.ssh_pass = data.get("sshPassword")
    cfg.proxy_host = data.get("proxyHost")
    if data.get("proxyPort"):
        try:
            cfg.proxy_port = int(data["proxyPort"])
        except (ValueError, TypeError):
            pass
    if data.get("connectionType"):
        cfg.protocol = cfg.protocol or str(data["connectionType"]).lower()
