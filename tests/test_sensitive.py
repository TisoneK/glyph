"""Sensitive stage: detectors, endpoint classification, risk, scan, CLI."""
from __future__ import annotations

import json

from glyph.catalog import Catalog, Flow
from glyph.cli import main
from glyph.sensitive import run_scan, scan_value
from glyph.sensitive.detectors import _luhn_ok, mask

_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123DEF456ghi789"


# -- detectors ------------------------------------------------------------
def test_detects_email_jwt_card():
    cats = {c for c, _, _ in scan_value("x", "reach me at a@b.com")}
    assert "email" in cats
    assert "jwt" in {c for c, _, _ in scan_value("token", _JWT)}
    assert "credit_card" in {c for c, _, _ in scan_value("cc", "4242 4242 4242 4242")}


def test_luhn_rejects_invalid_card():
    assert _luhn_ok("4242424242424242") is True
    assert _luhn_ok("1234567812345678") is False
    # invalid-Luhn digit run is not flagged as a card
    assert "credit_card" not in {c for c, _, _ in scan_value("x", "1234567812345678")}


def test_password_field_and_secret_gating():
    assert "password" in {c for c, _, _ in scan_value("password", "hunter2xyz")}
    # a high-entropy value in a NON-secret field is not flagged as a secret
    rnd = "Zx9Q2mvKpL7wRt3Ny8Bc4Df1Gh6Jk0"
    assert "secret_token" not in {c for c, _, _ in scan_value("nonce_display", rnd)}
    assert "secret_token" in {c for c, _, _ in scan_value("api_secret", rnd)}


def test_kenyan_phone():
    assert "phone_ke" in {c for c, _, _ in scan_value("msisdn", "+254712345678")}


def test_mask_is_display_only():
    assert mask("supersecret") == "supe*******"


# -- scan integration -----------------------------------------------------
def _scan(flows):
    cat = Catalog(":memory:")
    for f in flows:
        cat.add_flow(f)
    run_scan(cat)
    return cat


def test_scan_flags_sensitive_data_keeps_value():
    cat = _scan([Flow(method="POST", url="https://a.t/api/login", host="", path="",
                      resp_mime="application/json", status=200,
                      resp_body=json.dumps({"token": _JWT, "email": "x@y.com"}))])
    data = cat.findings(kind="sensitive_data")
    jwt = [f for f in data if f.category == "jwt"][0]
    assert jwt.value_sample.startswith("eyJ")  # value kept, not redacted
    cat.close()


def test_scan_flags_sensitive_endpoint():
    cat = _scan([Flow(method="GET", url="https://a.t/admin/users", host="", path="")])
    cats = {f.category for f in cat.findings(kind="sensitive_endpoint")}
    assert "admin_endpoint" in cats
    cat.close()


def test_unauthenticated_sensitive_data_is_critical():
    cat = _scan([Flow(method="POST", url="https://a.t/api/login", host="", path="",
                      resp_mime="application/json", status=200,
                      resp_body=json.dumps({"card": "4242 4242 4242 4242"}))])
    risk = {f.category: f for f in cat.findings(kind="risk")}
    assert "unauthenticated_sensitive_data" in risk
    assert risk["unauthenticated_sensitive_data"].severity == "critical"
    cat.close()


def test_secret_in_url_flagged():
    cat = _scan([Flow(method="GET", url="https://a.t/x?token=" + _JWT, host="", path="")])
    assert any(f.category == "sensitive_data_in_url"
               for f in cat.findings(kind="risk"))
    cat.close()


def test_wildcard_cors_with_creds_is_critical():
    cat = _scan([Flow(method="GET", url="https://a.t/x", host="", path="",
                      resp_headers={"Access-Control-Allow-Origin": "*",
                                    "Access-Control-Allow-Credentials": "true"})])
    cors = [f for f in cat.findings(kind="risk") if f.category == "wildcard_cors"]
    assert cors and cors[0].severity == "critical"
    cat.close()


def test_guessable_ids_idor():
    cat = _scan([
        Flow(method="GET", url="https://a.t/api/users/5", host="", path=""),
        Flow(method="GET", url="https://a.t/api/users/6", host="", path=""),
    ])
    assert any(f.category == "guessable_object_id"
               for f in cat.findings(kind="risk"))
    cat.close()


def test_rescan_is_idempotent():
    flows = [Flow(method="GET", url="https://a.t/admin", host="", path="")]
    cat = _scan(flows)
    n1 = len(cat.findings())
    run_scan(cat)  # again
    assert len(cat.findings()) == n1  # not doubled
    cat.close()


def test_min_severity_filter():
    cat = _scan([Flow(method="POST", url="https://a.t/api/login", host="", path="",
                      resp_mime="application/json",
                      resp_body=json.dumps({"card": "4242 4242 4242 4242"}))])
    highs = cat.findings(min_severity="high")
    assert highs and all(f.severity in ("critical", "high") for f in highs)
    cat.close()


# -- CLI ------------------------------------------------------------------
def test_cli_sensitive(tmp_path, make_entry, capsys):
    import glyph.capture  # noqa
    from glyph.capture import ingest_har
    db = str(tmp_path / "c.db")
    har = tmp_path / "s.har"
    har.write_text(json.dumps({"log": {"entries": [
        make_entry("POST", "https://a.t/api/login",
                   body=json.dumps({"token": _JWT})),
    ]}}))
    cat = Catalog(db)
    ingest_har(cat, str(har))
    cat.close()
    assert main(["sensitive", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "finding" in out.lower()
