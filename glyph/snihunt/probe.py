"""Optional active SNI probe (ADR-10).

Opens ONE TLS handshake to a public CDN edge with the candidate as the SNI
and records the served cert's CN/SAN — the "verify" step. This is exactly
what a browser does on every page load: no port scanning, no exploitation,
no fingerprinting beyond the cert. Default OFF; opt in with ``--probe``.

The probe confirms the candidate is reachable as an SNI on a real edge and
captures the cert lineage (which other names share the cert — a strong
fronting signal). It does NOT verify carrier zero-rating (that needs the
user's SIM on the target network; tracked as a backlog follow-up).
"""
from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProbeResult:
    host: str
    ip: str
    port: int
    ok: bool
    subject: Optional[str] = None
    sans: List[str] = field(default_factory=list)
    error: Optional[str] = None


def probe_sni(host: str, ip: Optional[str] = None, port: int = 443,
              timeout: float = 6.0) -> ProbeResult:
    """Open a TLS handshake with ``host`` as the SNI to ``ip`` (or resolved).

    Returns the cert's subject + SANs on success, or the error on failure.
    Never raises — a failed probe is a negative signal, not a crash.
    """
    # If the caller didn't give us an IP, resolve via the system resolver
    # (this path is opt-in / online; the DNS hunter already used DoH).
    target_ip = ip
    if not target_ip:
        try:
            target_ip = socket.gethostbyname(host)
        except socket.gaierror as exc:
            return ProbeResult(host=host, ip="", port=port, ok=False,
                               error=f"resolve failed: {exc}")
    ctx = ssl.create_default_context()
    # We want to READ the cert even if verification would fail (a self-signed
    # or mismatched cert is still a signal), so disable the verify hard-fail.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((target_ip, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                subject = dict(x[0] for x in (cert or {}).get("subject", []))
                cn = subject.get("commonName") if isinstance(subject, dict) else None
                sans_raw = (cert or {}).get("subjectAltName", [])
                sans = [v[1] for v in sans_raw if v[0] == "DNS"] if sans_raw else []
                return ProbeResult(host=host, ip=target_ip, port=port, ok=True,
                                   subject=cn, sans=sans)
    except (socket.timeout, OSError, ssl.SSLError) as exc:
        return ProbeResult(host=host, ip=target_ip or "", port=port, ok=False,
                           error=str(exc)[:200])
