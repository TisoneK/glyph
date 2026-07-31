"""Optional active SNI probe (ADR-10).

Opens ONE TLS handshake to a public CDN edge with the candidate as the SNI,
records the served cert's CN/SAN, AND sends an HTTP GET to record the status
code (200/301/403/…). This is exactly what a browser does on every page
load: no port scanning, no exploitation, no fingerprinting beyond the cert +
the HTTP response line. Default OFF; opt in with ``--probe``.

The probe confirms the candidate is reachable as an SNI on a real edge,
captures the cert lineage (which other names share the cert — a strong
fronting signal), and shows whether the host actually serves content (a dead
host is useless for tunnelling). It does NOT verify carrier zero-rating
(that needs the user's SIM on the target network; tracked as a backlog
follow-up).
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
    http_status: Optional[int] = None   # 200 / 301 / 403 / … (None if not reached)
    error: Optional[str] = None


def probe_sni(host: str, ip: Optional[str] = None, port: int = 443,
              timeout: float = 6.0) -> ProbeResult:
    """Open a TLS handshake with ``host`` as the SNI, then HTTP GET for status.

    Returns the cert's subject + SANs + the HTTP status code on success, or
    the error on failure. Never raises — a failed probe is a negative signal,
    not a crash.
    """
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
    # NOTE: with CERT_NONE, getpeercert() returns {} (no parsed cert). To get
    # the CN/SAN we use get_unverified_chain() + parse the binary DER. This
    # keeps the cert-capture working without enforcing validation.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((target_ip, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cn, sans = _cert_cn_sans(ssock)
                # Now send a minimal HTTP GET over the same TLS connection to
                # capture the status code. One request, read the first line of
                # the response (the status line) — we don't need the body.
                http_status = _http_status(ssock, host)
                return ProbeResult(host=host, ip=target_ip, port=port, ok=True,
                                   subject=cn, sans=sans, http_status=http_status)
    except (socket.timeout, OSError, ssl.SSLError) as exc:
        return ProbeResult(host=host, ip=target_ip or "", port=port, ok=False,
                           error=str(exc)[:200])


def _http_status(ssock: ssl.SSLSocket, host: str) -> Optional[int]:
    """Send a minimal HTTP/1.1 GET over ``ssock`` and parse the status code.

    Returns the integer status (200, 301, …) or None on any failure. We read
    only the status line — the body is irrelevant and would waste bandwidth.
    """
    try:
        req = (f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n"
               f"User-Agent: glyph-recon/0.1\r\n\r\n").encode("ascii")
        ssock.sendall(req)
        # Read enough to get the status line (first line of the response).
        chunks = []
        while sum(len(c) for c in chunks) < 1024:
            data = ssock.recv(512)
            if not data:
                break
            chunks.append(data)
            # Stop once we have the first CRLF (end of status line).
            buf = b"".join(chunks)
            if b"\r\n" in buf:
                break
        buf = b"".join(chunks)
        line = buf.split(b"\r\n", 1)[0].decode("ascii", "ignore")
        # "HTTP/1.1 200 OK" → 200
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
    except Exception:
        pass
    return None


def _cert_cn_sans(ssock: ssl.SSLSocket):
    """Extract the CN + SANs from the peer cert.

    With ``verify_mode=CERT_NONE`` (our default — we read certs without
    enforcing validation), ``getpeercert()`` returns ``{}``. We fall back to
    parsing the binary DER chain via ``ssl.DER_cert_to_PEM_cert`` + the
    stdlib ``_test_decode_cert`` helper. Returns ``(cn, sans)``; ``(None, [])``
    on any failure — cert capture is a bonus, the HTTP status is the point.
    """
    try:
        cert = ssock.getpeercert()
        if cert:
            subject = dict(x[0] for x in cert.get("subject", []))
            cn = subject.get("commonName") if isinstance(subject, dict) else None
            sans_raw = cert.get("subjectAltName", [])
            sans = [v[1] for v in sans_raw if v[0] == "DNS"] if sans_raw else []
            return cn, sans
        # CERT_NONE fallback: parse the binary DER leaf cert.
        der_chain = ssock.get_unverified_chain()
        if not der_chain:
            return None, []
        leaf_pem = ssl.DER_cert_to_PEM_cert(der_chain[0])
        # _test_decode_cert parses a PEM string into a dict (stdlib, stable
        # across 3.8–3.13 despite the leading underscore).
        import ssl as _ssl
        decode = getattr(_ssl, "_test_decode_cert", None)
        if decode is None:
            return None, []
        decoded = decode(leaf_pem)
        if not isinstance(decoded, dict):
            return None, []
        subject = dict(x[0] for x in decoded.get("subject", []))
        cn = subject.get("commonName") if isinstance(subject, dict) else None
        sans_raw = decoded.get("subjectAltName", [])
        sans = [v[1] for v in sans_raw if v[0] == "DNS"] if sans_raw else []
        return cn, sans
    except Exception:
        return None, []
