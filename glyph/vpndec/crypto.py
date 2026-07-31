"""Crypto primitives for the VPN-Config Decoder (ADR-11).

All crypto goes through this module so the ``HAS_CRYPTO`` flag gates it in
one place. pycryptodome (``Crypto.Cipher.AES``) is the backend — an optional
``[crypto]`` extra. If it's absent, the functions return ``None`` and the
decryptors degrade to ``no_decryptor`` for crypto-dependent formats (plain
formats like the DARK envelope still decode).

Ported from InjectX's per-decryptor helpers, centralized here.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Optional

try:
    from Crypto.Cipher import AES, ChaCha20_Poly1305
    from Crypto.Protocol.KDF import PBKDF2
    from Crypto.Hash import SHA256
    HAS_CRYPTO = True
except ImportError:  # pragma: no cover
    HAS_CRYPTO = False


# ── AES ──────────────────────────────────────────────────────────────────────

def aes_ecb_decrypt(ciphertext: bytes, key: bytes) -> Optional[bytes]:
    """AES-ECB decryption with PKCS7 padding removal. None on any failure."""
    if not HAS_CRYPTO:
        return None
    try:
        cipher = AES.new(key, AES.MODE_ECB)
        decrypted = cipher.decrypt(ciphertext)
        pad_len = decrypted[-1]
        if 1 <= pad_len <= 16 and all(b == pad_len for b in decrypted[-pad_len:]):
            decrypted = decrypted[:-pad_len]
        return decrypted
    except Exception:
        return None


def aes_cbc_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> Optional[bytes]:
    """AES-CBC decryption with PKCS7 padding removal. None on any failure."""
    if not HAS_CRYPTO:
        return None
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(ciphertext)
        pad_len = decrypted[-1]
        ks = len(key)
        if 1 <= pad_len <= ks and all(b == pad_len for b in decrypted[-pad_len:]):
            decrypted = decrypted[:-pad_len]
        return decrypted
    except Exception:
        return None


def aes_gcm_decrypt(ciphertext: bytes, key: bytes, iv: bytes,
                    tag: bytes) -> Optional[bytes]:
    """AES-GCM decryption with auth-tag verification. None on MAC failure."""
    if not HAS_CRYPTO:
        return None
    try:
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        return cipher.decrypt_and_verify(ciphertext, tag)
    except Exception:
        return None


# ── KDF ──────────────────────────────────────────────────────────────────────

def pbkdf2_sha256(password: bytes, salt: bytes, dkLen: int = 32,
                  count: int = 1000) -> Optional[bytes]:
    """PBKDF2-HMAC-SHA256 key derivation. None if pycryptodome is absent."""
    if not HAS_CRYPTO:
        return None
    try:
        return PBKDF2(password, salt, dkLen=dkLen, count=count,
                      hmac_hash_module=SHA256)
    except Exception:
        return None


# ── Key derivation helpers ───────────────────────────────────────────────────

def sha1_key16(password: str) -> bytes:
    """SHA1(password)[:16] — the AES-128 key derivation HC uses."""
    return hashlib.sha1(password.encode("utf-8")).digest()[:16]


# ── Base64 helpers ───────────────────────────────────────────────────────────

def b64_decode_tolerant(s: str) -> Optional[bytes]:
    """Decode base64 that may be URL-safe and/or missing padding."""
    try:
        s = s.strip().replace("-", "+").replace("_", "/")
        s += "=" * ((-len(s)) % 4)
        return base64.b64decode(s)
    except Exception:
        return None


_STD_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def custom_b64_decode(encoded: str, charset: str, padding: str = "?") -> Optional[bytes]:
    """Decode a string using a custom base64 charset (EHI's variant)."""
    try:
        trans = str.maketrans(charset[:64], _STD_B64[:64])
        standardized = encoded.replace(padding, "=").translate(trans)
        missing = len(standardized) % 4
        if missing:
            standardized += "=" * (4 - missing)
        return base64.b64decode(standardized)
    except Exception:
        return None


# ── XOR helpers ──────────────────────────────────────────────────────────────

def xor_string(data: str, key: str) -> str:
    """Repeating XOR over a string: data[i] ^ key[i % len(key)]."""
    return "".join(chr(ord(ch) ^ ord(key[i % len(key)]))
                   for i, ch in enumerate(data))
