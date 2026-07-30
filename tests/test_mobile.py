"""Mobile: static URL/API-path mining from an app package."""
from __future__ import annotations

import zipfile

from glyph.mobile import mine_apk, mine_apk_to_catalog


def _fake_apk(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "classes.dex",
            b"junk\x00https://api.example.com/v1/login junk"
            b"\x00'/api/users/{id}'\x00https://cdn.example.com/x.png")
        zf.writestr("res/raw/config.json",
                    b'{"base":"https://api.example.com/v2/orders"}')
    return str(path)


def test_mine_apk_finds_urls_and_paths(tmp_path):
    apk = _fake_apk(tmp_path / "app.apk")
    res = mine_apk(apk)
    assert "https://api.example.com/v1/login" in res["urls"]
    assert "api.example.com" in res["hosts"]
    assert "/api/users/{id}" in res["api_paths"]


def test_mine_apk_to_catalog_records_endpoints(catalog, tmp_path):
    apk = _fake_apk(tmp_path / "app.apk")
    res = mine_apk_to_catalog(catalog, apk)
    assert res["endpoints_added"] >= 2
    keys = {e.key for e in catalog.endpoints()}
    assert any("api.example.com" in k for k in keys)
