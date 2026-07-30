"""Auth analysis — classify each endpoint's authentication + request signing.

Inspects observed request headers and query strings for auth schemes
(Bearer/Basic/API-key/cookie) and for request-signing patterns (an
hmac/signature parameter alongside a timestamp/nonce). Domain-neutral;
reads only what capture already recorded.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Set

from glyph.catalog import Catalog

_APIKEY_HEADERS = ("x-api-key", "apikey", "api-key", "x-auth-token",
                   "x-access-token")
_APIKEY_QUERY = ("api_key", "apikey", "key", "access_token", "token",
                 "auth", "app_key", "client_secret")
_SIGN_PARAMS = ("signature", "sign", "sig", "hmac", "hash", "checksum", "mac")
_NONCE_PARAMS = ("timestamp", "ts", "time", "nonce", "expires", "expire",
                 "_", "salt")


def _scheme_of(auth_header: str) -> str:
    token = auth_header.split(" ", 1)[0].lower()
    return {
        "bearer": "Bearer token",
        "basic": "HTTP Basic",
        "digest": "HTTP Digest",
        "negotiate": "SPNEGO/Kerberos",
    }.get(token, f"Authorization: {token or 'unknown'}")


def analyze(catalog: Catalog) -> Dict[str, Dict[str, Any]]:
    """Return ``{endpoint_key: {schemes, signed, signing_params, evidence}}``."""
    endpoints = {e.id: e for e in catalog.endpoints()}
    acc: Dict[int, Dict[str, Any]] = defaultdict(
        lambda: {"schemes": set(), "signed": False,
                 "signing_params": set(), "evidence": []})

    for flow in catalog.all_flows():
        ep_id = _endpoint_id(catalog, flow)
        if ep_id is None:
            continue
        rec = acc[ep_id]
        headers = {k.lower(): v for k, v in (flow.req_headers or {}).items()}

        if "authorization" in headers:
            rec["schemes"].add(_scheme_of(headers["authorization"]))
        for h in _APIKEY_HEADERS:
            if h in headers:
                rec["schemes"].add(f"API key ({h})")
        if "cookie" in headers:
            rec["schemes"].add("Cookie/session")

        params = {k.lower() for k in (flow.query or {})}
        for p in _APIKEY_QUERY:
            if p in params:
                rec["schemes"].add(f"API key (query: {p})")
        signing = _signing_params(params)
        if signing:
            rec["signed"] = True
            rec["signing_params"].update(signing)
            rec["evidence"].append(
                "signed request (params: " + ", ".join(sorted(signing)) + ")")

    out: Dict[str, Dict[str, Any]] = {}
    for ep_id, rec in acc.items():
        ep = endpoints.get(ep_id)
        key = ep.key if ep else str(ep_id)
        schemes = sorted(rec["schemes"]) or ["none observed"]
        out[key] = {
            "schemes": schemes,
            "signed": rec["signed"],
            "signing_params": sorted(rec["signing_params"]),
            "evidence": list(dict.fromkeys(rec["evidence"])) or schemes,
        }
    return out


def _signing_params(params: Set[str]) -> Set[str]:
    sig = {p for p in params if any(s in p for s in _SIGN_PARAMS)}
    if not sig:
        return set()
    # Nonce/timestamp params match exactly — substring matching pulls in
    # unrelated keys (the bare "_" cache-buster would hit "api_key").
    nonce = {p for p in params if p in _NONCE_PARAMS}
    return sig | nonce


def _endpoint_id(catalog: Catalog, flow: Any) -> Any:
    from glyph.catalog.normalize import template_path
    row = catalog.conn.execute(
        "SELECT id FROM endpoints WHERE method=? AND host=? AND path_template=?",
        (flow.method.upper(), flow.host, template_path(flow.path)),
    ).fetchone()
    return row["id"] if row else None
