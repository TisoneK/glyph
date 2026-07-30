"""Fingerprint, auth, and gating analyzers."""
from __future__ import annotations

from glyph.auth import analyze
from glyph.capture import ingest_har
from glyph.fingerprint import fingerprint
from glyph.gating import profile


def test_fingerprint_from_cookie_and_server(catalog, har_file, make_entry):
    ingest_har(catalog, har_file([make_entry(
        "GET", "https://s.t/x",
        resp_headers={"Server": "nginx", "Set-Cookie": "laravel_session=a; Path=/"})]))
    fp = fingerprint(catalog)["s.t"]
    assert fp["server"] == "nginx"
    assert "Laravel (PHP)" in fp["frameworks"]


def test_auth_detects_bearer_and_signing(catalog, har_file, make_entry):
    ingest_har(catalog, har_file([make_entry(
        "GET", "https://s.t/o?sign=abc&ts=1&api_key=k",
        req_headers={"Authorization": "Bearer tok"})]))
    rec = analyze(catalog)["GET s.t/o"]
    assert "Bearer token" in rec["schemes"]
    assert rec["signed"] is True
    assert set(rec["signing_params"]) == {"sign", "ts"}
    assert "api_key" not in rec["signing_params"]  # auth, not a signing param


def test_gating_rate_limit_and_bot_mgmt(catalog, har_file, make_entry):
    ingest_har(catalog, har_file([
        make_entry("GET", "https://s.t/o", status=429,
                   resp_headers={"Retry-After": "30"}),
        make_entry("GET", "https://s.t/o",
                   resp_headers={"cf-ray": "88a", "X-RateLimit-Limit": "100"}),
    ]))
    g = profile(catalog)["s.t"]
    assert g["rate_limited"] is True
    assert "Cloudflare" in g["bot_management"]
    assert "retry-after" in g["rate_limit_headers"]
