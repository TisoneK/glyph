"""HTTP Injector (.ehi) decryption — scheme B1 (ADR-11).

Two-stage AES + field-level XOR with a custom base64 charset.
  Stage 1: AES-256-CBC (brute-forced key × IV combinations)
  Stage 2: AES-128-CBC on the last-colon segment
  Stage 3: field deobfuscation (reverse + custom base64 + XOR with configSalt)

Custom base64 charset (EHI variant):
  RkLC2QaVMPYgGJW/A4f7qzDb9e+t6Hr0Zp8OlNyjuxKcTw1o5EIimhBn3UvdSFXs?
  Padding: ? (instead of =)

Ported from InjectX ``backend/decrypt/ehi_decrypt.py``.
Algorithms credit: Pancho7532/HCDecryptor evoziDecryptor.lib.js.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from glyph.vpndec import crypto
from glyph.vpndec.keys import KeyStore
from glyph.vpndec.models import DecryptStatus, Scheme, VpnConfig

_EHI_B64 = "RkLC2QaVMPYgGJW/A4f7qzDb9e+t6Hr0Zp8OlNyjuxKcTw1o5EIimhBn3UvdSFXs?"
_EHI_PADDING = "?"
_KNOWN_EHI = {"Payload", "PayloadMethod", "PayloadURL", "RemoteProxy",
              "RemoteProxyPort", "SSHHost", "SSHPort", "SSHUser", "SSHPassword",
              "SSL", "DNS", "OnlineHost", "ProxyType", "Version", "V2Ray",
              "configSalt"}
_OBFUSCATED_FIELDS = ["host", "user", "password", "remoteProxy", "payload",
                      "sniHostname", "shadowsocksConfig", "httpObfsSettings",
                      "v2rWsPath"]


def _deobfuscate_field(value: str, config_salt: str) -> Optional[str]:
    """Reverse → custom-b64 decode → hex→chars → XOR with configSalt."""
    try:
        decoded = crypto.custom_b64_decode(value[::-1], _EHI_B64, _EHI_PADDING)
        if decoded is None:
            return None
        hex_str = decoded.hex()
        pre = "".join(chr(int(hex_str[i:i + 2], 16))
                      for i in range(0, len(hex_str) - 1, 2))
        return crypto.xor_string(pre, config_salt)
    except Exception:
        return None


def _score(data: Dict[str, Any]) -> float:
    if not data:
        return 0.0
    keys = set(data.keys())
    overlap = len(keys & _KNOWN_EHI)
    score = 0.3 + min(0.3, overlap * 0.03)
    if data.get("SSHHost") or data.get("SSHUser"):
        score += 0.15
    if data.get("Payload"):
        score += 0.15
    if data.get("RemoteProxy"):
        score += 0.1
    return min(1.0, score)


def decrypt_ehi(raw: bytes, keys: KeyStore, filename: str,
                filepath: str) -> VpnConfig:
    """Decrypt an HTTP Injector .ehi config (scheme B1)."""
    evozi = keys.evozi
    aes256_keys = evozi[0]
    aes128_keys = evozi[1] if len(evozi) > 1 else []
    ivs = evozi[2] if len(evozi) > 2 else []

    if not aes256_keys or not ivs or not crypto.HAS_CRYPTO:
        return VpnConfig(
            filepath=filepath, filename=filename, format="ehi",
            is_encrypted=True,
            decryption_status=DecryptStatus.NO_DECRYPTOR,
            scheme=Scheme.B1, confidence=0.0,
            errors=["pycryptodome not installed (pip install 'glyph-re[crypto]')"
                    if not crypto.HAS_CRYPTO else "no evozi keys available"],
        )

    # Strip the EHI header (40 bytes regular, 41 for Lite).
    is_lite = b"ehil" in raw[:50]
    offset = 41 if is_lite else 40
    payload_data = raw[offset:]

    # Stage 1: AES-256-CBC — find a key×IV that yields a base64-like last segment.
    best_s1: Optional[tuple] = None  # (last_segment, key_label)
    for key_b64 in aes256_keys:
        key = crypto.b64_decode_tolerant(key_b64)
        if key is None:
            continue
        for iv_str in ivs:
            iv = iv_str.encode("utf-8")[:16]
            dec = crypto.aes_cbc_decrypt(payload_data, key, iv)
            if dec is None:
                continue
            try:
                text = dec.decode("utf-8", "strict")
            except Exception:
                continue
            last_seg = text.rsplit(":", 1)[-1] if ":" in text else text
            if len(last_seg) > 20:
                best_s1 = (last_seg.encode("utf-8"), f"S1:{key_b64[:12]}…+IV:{iv_str}")
                break
        if best_s1:
            break

    if best_s1 is None:
        return VpnConfig(
            filepath=filepath, filename=filename, format="ehi",
            is_encrypted=True, decryption_status=DecryptStatus.FAILED,
            scheme=Scheme.B1, confidence=0.0,
            errors=["stage 1 (AES-256-CBC) failed for all key×IV combos"],
        )

    stage1_data, s1_label = best_s1

    # Stage 2: AES-128-CBC on the last segment → JSON with configSalt.
    for key_b64 in aes128_keys:
        key = crypto.b64_decode_tolerant(key_b64)
        if key is None:
            continue
        for iv_str in ivs:
            iv = iv_str.encode("utf-8")[:16]
            dec = crypto.aes_cbc_decrypt(stage1_data, key, iv)
            if dec is None:
                continue
            try:
                text = dec.decode("utf-8", "strict")
            except Exception:
                continue
            if "configSalt" not in text:
                continue
            # Fix the malformed JSON prefix (first 17 chars are junk).
            for fixed in ('{"a":"' + text[17:], '{"a"' + text[14:]):
                try:
                    data = json.loads(fixed)
                    break
                except json.JSONDecodeError:
                    data = None
            if not data:
                continue

            # Stage 3: deobfuscate the sensitive fields.
            config_salt = data.get("configSalt", "EVZJNI")
            for field in _OBFUSCATED_FIELDS:
                v = data.get(field)
                if isinstance(v, str) and v:
                    deob = _deobfuscate_field(v, config_salt)
                    if deob:
                        data[field] = deob

            conf = _score(data)
            status = (DecryptStatus.SUCCESS if conf >= 0.5
                      else DecryptStatus.PARTIAL)
            cfg = VpnConfig(
                filepath=filepath, filename=filename, format="ehi",
                is_encrypted=True, decryption_status=status, scheme=Scheme.B1,
                confidence=conf, key_label=f"{s1_label}+S2:{key_b64[:12]}…",
                raw_data=data,
            )
            _populate_from_ehi(cfg, data)
            return cfg

    return VpnConfig(
        filepath=filepath, filename=filename, format="ehi",
        is_encrypted=True, decryption_status=DecryptStatus.FAILED,
        scheme=Scheme.B1, confidence=0.0,
        errors=["stage 2 (AES-128-CBC) failed — no configSalt in any decode"],
    )


def _populate_from_ehi(cfg: VpnConfig, data: Dict[str, Any]) -> None:
    """Lift common fields off a decrypted EHI dict."""
    cfg.payload = data.get("Payload") or data.get("payload")
    cfg.sni = data.get("sniHostname") or data.get("SNI")
    cfg.dns = data.get("DNS") or data.get("dns")
    cfg.remote_dns = data.get("OnlineHost")
    ssh = data.get("SSHHost") or data.get("host")
    if ssh:
        cfg.ssh_server = ssh
        cfg.host = ssh
        cfg.protocol = "ssh"
    port = data.get("SSHPort") or data.get("SSHPort2")
    if port:
        try:
            cfg.ssh_port = int(port)
            cfg.port = cfg.ssh_port
        except (ValueError, TypeError):
            pass
    cfg.ssh_user = data.get("SSHUser") or data.get("user")
    cfg.ssh_pass = data.get("SSHPassword") or data.get("password")
    proxy = data.get("RemoteProxy") or data.get("remoteProxy")
    if proxy:
        cfg.proxy_host = proxy
    pport = data.get("RemoteProxyPort") or data.get("proxyPort")
    if pport:
        try:
            cfg.proxy_port = int(pport)
        except (ValueError, TypeError):
            pass
