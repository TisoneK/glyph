"""Sensitive-data detectors — PII, secrets, and financial values.

Pure-stdlib pattern matching over already-captured values. Each detector
returns the *category*, a *severity*, and the *matched substring* — which
is KEPT (this is a reverse-engineering tool; the value is the point). High
false-positive detectors (generic secrets) are gated on the field name so
random ids don't get flagged.
"""
from __future__ import annotations

import math
import re
from typing import List, Optional, Tuple

from glyph.catalog import SEV_CRITICAL, SEV_HIGH, SEV_LOW, SEV_MEDIUM

# (category, compiled regex, severity). Order matters only for readability.
_PATTERNS: List[Tuple[str, "re.Pattern", str]] = [
    ("private_key",
     re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
     SEV_CRITICAL),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), SEV_HIGH),
    ("jwt",
     re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"),
     SEV_HIGH),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), SEV_HIGH),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}"), SEV_HIGH),
    ("email",
     re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
     SEV_MEDIUM),
    ("ssn_us", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), SEV_HIGH),
    ("iban",
     re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"), SEV_MEDIUM),
    # Kenyan mobile (Safaricom/M-Pesa) — Kenya-priority target surface.
    ("phone_ke", re.compile(r"\b(?:\+?254|0)7\d{8}\b"), SEV_MEDIUM),
    ("phone_intl", re.compile(r"\+\d{1,3}[\s-]?\d{3}[\s-]?\d{3,4}[\s-]?\d{3,4}\b"),
     SEV_LOW),
]

# Candidate card-number shape (13-19 digits, spaces/dashes allowed).
_CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){13,19}\b")

# Field/param names that make a high-entropy value a likely secret.
_SECRET_NAME = re.compile(
    r"(secret|token|passwd|password|pwd|apikey|api_key|access_key|"
    r"auth|signature|sign|session|credential|private)", re.IGNORECASE)
# Field names that are explicitly a credential value.
_PASSWORD_NAME = re.compile(r"^(password|passwd|pwd|pass)$", re.IGNORECASE)

_ENTROPY_MIN = 3.6      # bits/char — random-looking
_ENTROPY_MIN_LEN = 20


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _luhn_ok(digits: str) -> bool:
    digits = re.sub(r"\D", "", digits)
    if not (13 <= len(digits) <= 19):
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _looks_like_card(candidate: str) -> bool:
    """Luhn-valid AND starts with a real card-network digit (3-6).

    Luhn alone false-positives on 13-19 digit numbers like Unix-ms
    timestamps; every live card network (Amex/Diners 3, Visa 4, Mastercard
    5, Discover/others 6) begins 3-6, so gate on that.
    """
    digits = re.sub(r"\D", "", candidate)
    return bool(digits) and digits[0] in "3456" and _luhn_ok(digits)


def scan_value(name: str, value: object) -> List[Tuple[str, str, str]]:
    """Return ``[(category, severity, matched_value)]`` for one value.

    ``name`` is the field/param/header name (used to gate generic secret
    detection). ``value`` is coerced to ``str`` for matching.
    """
    if value is None or isinstance(value, bool):
        return []
    text = value if isinstance(value, str) else str(value)
    if not text or len(text) > 20000:
        return []
    out: List[Tuple[str, str, str]] = []

    for category, pattern, sev in _PATTERNS:
        m = pattern.search(text)
        if m:
            out.append((category, sev, m.group(0)))

    # Credit card: shape + Luhn + card-network prefix (3-6). The prefix
    # gate rejects Luhn-valid non-cards like millisecond timestamps.
    for m in _CARD_CANDIDATE.finditer(text):
        if _looks_like_card(m.group(0)):
            out.append(("credit_card", SEV_HIGH, m.group(0).strip()))
            break

    # Explicit credential field by name.
    if _PASSWORD_NAME.match(name or "") and text.strip():
        out.append(("password", SEV_HIGH, text))

    # Generic secret: high-entropy value in a secret-named field.
    if (_SECRET_NAME.search(name or "")
            and len(text) >= _ENTROPY_MIN_LEN
            and " " not in text
            and _shannon_entropy(text) >= _ENTROPY_MIN
            and not any(c[0] in ("jwt", "aws_access_key", "password")
                        for c in out)):
        out.append(("secret_token", SEV_HIGH, text))

    # De-dupe by (category, value).
    seen = set()
    deduped = []
    for cat, sev, val in out:
        key = (cat, val)
        if key not in seen:
            seen.add(key)
            deduped.append((cat, sev, val))
    return deduped


def mask(value: Optional[str], keep: int = 4) -> str:
    """Mask a value for *display/export only* (never mutates the catalog)."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)
