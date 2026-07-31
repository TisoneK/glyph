"""Sensitive-endpoint classification — by path shape.

Flags endpoints whose path marks them as security-relevant (auth, admin,
payment, account, credential, export, debug). This is orthogonal to the
data flowing through them; the risk stage cross-links "sensitive endpoint
+ no auth + sensitive data" into higher-severity findings.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from glyph.catalog import (
    FINDING_SENSITIVE_ENDPOINT,
    SEV_HIGH,
    SEV_MEDIUM,
    Catalog,
    Finding,
)
from glyph.sensitive import party as party_mod

# (compiled path regex, category, severity). Matched against the lowercased
# path template. First-match-wins ordering: most specific / severe first.
_RULES: List[Tuple["re.Pattern", str, str]] = [
    (re.compile(r"/(\.env|\.git|actuator|phpinfo|server-status|debug|"
                r"_debug|internal|trace|metrics)(/|$)"),
     "debug_or_internal_endpoint", SEV_HIGH),
    (re.compile(r"/(admin|administrator|superuser|manage|console)(/|$)"),
     "admin_endpoint", SEV_HIGH),
    (re.compile(r"/(login|signin|sign-in|logout|register|signup|sign-up|"
                r"oauth|token|session|sso|saml|auth)(/|$)"),
     "auth_endpoint", SEV_HIGH),
    (re.compile(r"/(password|passwd|reset|forgot|change-password|"
                r"credential)(/|$)"),
     "credential_endpoint", SEV_HIGH),
    (re.compile(r"/(payment|pay|checkout|billing|invoice|charge|card|refund|"
                r"stripe|paypal|mpesa|daraja|stkpush|wallet)(/|$)"),
     "payment_endpoint", SEV_HIGH),
    (re.compile(r"/(export|download|backup|dump|report)(/|$)"),
     "data_export_endpoint", SEV_MEDIUM),
    (re.compile(r"/(upload|files?)(/|$)"),
     "upload_endpoint", SEV_MEDIUM),
    (re.compile(r"/(account|users?|profile|customers?|me|contacts?|"
                r"address)(/|$)"),
     "account_endpoint", SEV_MEDIUM),
]


def classify(catalog: Catalog, target: Optional[str] = None) -> List[Finding]:
    """Return sensitive-endpoint findings for the catalog's endpoints."""
    findings: List[Finding] = []
    for ep in catalog.endpoints():
        path = (ep.path_template or "").lower()
        for pattern, category, sev in _RULES:
            if pattern.search(path):
                findings.append(Finding(
                    kind=FINDING_SENSITIVE_ENDPOINT,
                    category=category,
                    severity=sev,
                    location="endpoint",
                    evidence=f"{ep.method} {ep.host}{ep.path_template} "
                             f"matches {category.replace('_', ' ')}",
                    endpoint_id=ep.id,
                    party=party_mod.classify(ep.host, target),
                ))
                break  # one classification per endpoint (most severe first)
    return findings
