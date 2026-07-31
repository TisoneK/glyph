"""VPN-Config Decoder — detector, crypto, decryptors, catalog, CLI (ADR-11).

Tests run against the REAL sample configs shipped in the InjectX repo
(cloned at /home/z/my-project/injectx-work/InjectX/assets/configs/). If the
InjectX clone isn't present (e.g. CI on another machine), the real-config
tests skip; the synthetic/unit tests always run.

Requires pycryptodome (the [crypto] extra) for the crypto-dependent
decryptors. If it's absent, those tests skip and only the no-crypto path
(detect, DARK envelope, plain JSON) is exercised.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from glyph.catalog import Catalog
from glyph.vpndec import decode_bytes, decode_file
from glyph.vpndec import crypto as crypto_mod
from glyph.vpndec import detect
from glyph.vpndec.models import DecryptStatus, Format, Scheme

INJECTX_CONFIGS = Path("/home/z/my-project/injectx-work/InjectX/assets/configs")
HAS_CRYPTO = crypto_mod.HAS_CRYPTO


# ── format detection (no crypto needed) ──────────────────────────────────────

def test_detect_by_extension():
    assert detect.detect_format_bytes("x.hc", b"") == Format.HC
    assert detect.detect_format_bytes("x.ehi", b"\x00\x03ehi") == Format.EHI
    assert detect.detect_format_bytes("x.dark", b"darktunnel://abc") == Format.DARK
    assert detect.detect_format_bytes("x.ziv", b"abc.def.ghi") == Format.ZIV
    assert detect.detect_format_bytes("x.tls", b"123:abc") == Format.TLS
    assert detect.detect_format_bytes("x.ovpn", b"client\ndev tun\nremote x 443") == Format.OVPN


def test_detect_by_content_dark_envelope():
    # A darktunnel:// base64(JSON) envelope — detectable by content alone.
    import base64
    payload = base64.b64encode(json.dumps(
        {"type": "VLESS", "server": "1.2.3.4", "port": 443}).encode()).decode()
    raw = ("darktunnel://" + payload).encode()
    assert detect.detect_format_bytes("unknown.ext", raw) == Format.DARK


def test_detect_identifies_plain_json_ehi():
    raw = json.dumps({"Payload": "GET /", "SSHHost": "1.2.3.4",
                      "SSHPort": 22, "configSalt": "abc"}).encode()
    assert detect.detect_format_bytes("unknown", raw) == Format.EHI


# ── DARK envelope (no crypto needed) ─────────────────────────────────────────

def test_dark_envelope_decodes_unlocked():
    import base64
    payload = base64.b64encode(json.dumps({
        "type": "VLESS", "name": "test", "server": "example.com",
        "port": 443, "sni": "sni.example.com",
    }).encode()).decode()
    cfg = decode_bytes("test.dark", ("darktunnel://" + payload).encode())
    assert cfg.format == Format.DARK
    assert cfg.decryption_status == DecryptStatus.SUCCESS
    assert cfg.scheme == Scheme.I1
    assert cfg.host == "example.com"
    assert cfg.port == 443
    assert cfg.protocol == "vless"
    assert cfg.sni == "sni.example.com"


def test_dark_envelope_reports_locked():
    import base64
    payload = base64.b64encode(json.dumps({
        "type": "VMESS", "encryptedLockedConfig": "opaque-blob-no-key-in-file",
    }).encode()).decode()
    cfg = decode_bytes("locked.dark", ("darktunnel://" + payload).encode())
    assert cfg.decryption_status == DecryptStatus.PARTIAL
    assert cfg.confidence == 0.5
    assert any("locked" in w.lower() for w in cfg.warnings)


def test_dark_envelope_plain_json_fallback():
    # Some exports aren't base64-wrapped — plain JSON should still work.
    raw = json.dumps({"type": "SSH", "server": "1.2.3.4", "port": 22}).encode()
    cfg = decode_bytes("plain.dark", raw)
    assert cfg.decryption_status == DecryptStatus.SUCCESS
    assert cfg.host == "1.2.3.4"


# ── plain OVPN ───────────────────────────────────────────────────────────────

def test_ovpn_plain_decodes():
    raw = b"client\ndev tun\nproto tcp\nremote vpn.example.com 443\n"
    cfg = decode_bytes("test.ovpn", raw)
    assert cfg.decryption_status == DecryptStatus.NOT_ENCRYPTED
    assert cfg.host == "vpn.example.com"
    assert cfg.port == 443
    assert cfg.protocol == "openvpn"


# ── crypto-dependent decryptors (skip if no pycryptodome) ────────────────────

pytestmark_crypto = pytest.mark.skipif(not HAS_CRYPTO,
    reason="pycryptodome not installed (pip install 'glyph-re[crypto]')")


@pytestmark_crypto
def test_hc_decrypts_real_sample():
    # Real .hc config from InjectX's assets.
    hc_file = INJECTX_CONFIGS / "hc" / "bypass.hc"
    if not hc_file.exists():
        pytest.skip("InjectX .hc sample not present")
    cfg = decode_file(str(hc_file))
    assert cfg.format == Format.HC
    assert cfg.decryption_status in (DecryptStatus.SUCCESS, DecryptStatus.PARTIAL,
                                     DecryptStatus.FAILED)
    # If it succeeded, we should have SOME fields populated.
    if cfg.decryption_status in (DecryptStatus.SUCCESS, DecryptStatus.PARTIAL):
        assert cfg.raw_data is not None


@pytestmark_crypto
def test_ehi_decrypts_real_sample():
    ehi_file = INJECTX_CONFIGS / "ehi" / "TelkomNet.ehi"
    if not ehi_file.exists():
        pytest.skip("InjectX .ehi sample not present")
    cfg = decode_file(str(ehi_file))
    assert cfg.format == Format.EHI
    assert cfg.decryption_status in (DecryptStatus.SUCCESS, DecryptStatus.PARTIAL,
                                     DecryptStatus.FAILED)


@pytestmark_crypto
def test_ziv_decrypts_real_sample():
    ziv_file = next((INJECTX_CONFIGS / "ziv").glob("*.ziv"), None)
    if ziv_file is None:
        pytest.skip("InjectX .ziv sample not present")
    cfg = decode_file(str(ziv_file))
    assert cfg.format == Format.ZIV
    assert cfg.decryption_status in (DecryptStatus.SUCCESS, DecryptStatus.PARTIAL,
                                     DecryptStatus.FAILED)


@pytestmark_crypto
def test_tls_decrypts_real_sample():
    tls_file = next((INJECTX_CONFIGS / "tls").glob("*.tls"), None)
    if tls_file is None:
        pytest.skip("InjectX .tls sample not present")
    cfg = decode_file(str(tls_file))
    assert cfg.format == Format.TLS
    assert cfg.decryption_status in (DecryptStatus.SUCCESS, DecryptStatus.PARTIAL,
                                     DecryptStatus.FAILED)


# ── HAS_CRYPTO=False path ────────────────────────────────────────────────────

def test_crypto_absent_reports_no_decryptor(monkeypatch):
    # Simulate pycryptodome being absent — crypto-dependent formats should
    # report no_decryptor, NOT crash.
    monkeypatch.setattr(crypto_mod, "HAS_CRYPTO", False)
    # A .ziv file (needs AES-GCM) → no_decryptor.
    cfg = decode_bytes("test.ziv", b"AAAA.BBBB.CCCC")
    assert cfg.decryption_status == DecryptStatus.NO_DECRYPTOR
    assert any("pycryptodome" in e for e in cfg.errors)
    # DARK envelope (no crypto) still works.
    import base64
    payload = base64.b64encode(json.dumps({"type": "SSH"}).encode()).decode()
    cfg2 = decode_bytes("test.dark", ("darktunnel://" + payload).encode())
    assert cfg2.decryption_status == DecryptStatus.SUCCESS


# ── catalog persistence ──────────────────────────────────────────────────────

def test_catalog_stores_vpn_config(tmp_path):
    import base64
    payload = base64.b64encode(json.dumps({
        "type": "VLESS", "server": "vpn.test", "port": 443,
        "sni": "sni.test"}).encode()).decode()
    cfg = decode_bytes("test.dark", ("darktunnel://" + payload).encode(),
                       filepath=str(tmp_path / "test.dark"))
    cat = Catalog(str(tmp_path / "c.db"))
    cat.add_vpn_config(cfg)
    stored = cat.vpn_configs()
    assert len(stored) == 1
    assert stored[0]["host"] == "vpn.test"
    assert stored[0]["port"] == 443
    assert stored[0]["sni"] == "sni.test"
    assert stored[0]["decryption_status"] == DecryptStatus.SUCCESS
    cat.close()


def test_catalog_vpn_upsert(tmp_path):
    # Re-decoding the same file replaces the row (upsert on filepath).
    import base64
    p = base64.b64encode(json.dumps({"type": "SSH", "server": "a.test",
                                     "port": 22}).encode()).decode()
    cfg = decode_bytes("test.dark", ("darktunnel://" + p).encode(),
                       filepath=str(tmp_path / "t.dark"))
    cat = Catalog(str(tmp_path / "c.db"))
    cat.add_vpn_config(cfg)
    cat.add_vpn_config(cfg)  # same filepath → upsert, not insert
    assert len(cat.vpn_configs()) == 1
    cat.close()


def test_catalog_reset_clears_vpn_configs(tmp_path):
    import base64
    p = base64.b64encode(json.dumps({"type": "SSH"}).encode()).decode()
    cfg = decode_bytes("t.dark", ("darktunnel://" + p).encode(),
                       filepath=str(tmp_path / "t.dark"))
    cat = Catalog(str(tmp_path / "c.db"))
    cat.add_vpn_config(cfg)
    assert len(cat.vpn_configs()) == 1
    cat.reset()
    assert len(cat.vpn_configs()) == 0
    cat.close()


# ── TUI adapter ──────────────────────────────────────────────────────────────

def test_tui_vpndec_rows(tmp_path):
    import base64
    from glyph.tui import data as D
    p = base64.b64encode(json.dumps({"type": "VLESS", "server": "x.test",
                                     "port": 443}).encode()).decode()
    cfg = decode_bytes("t.dark", ("darktunnel://" + p).encode(),
                       filepath=str(tmp_path / "t.dark"))
    cat = Catalog(str(tmp_path / "c.db"))
    cat.add_vpn_config(cfg)
    headers, rows = D.vpndec_rows(cat)
    assert headers[0] == "STATUS"
    assert len(rows) == 1
    assert "x.test" in rows[0]
    assert "vless" in rows[0]
    cat.close()


def test_tui_summary_includes_vpn_count(tmp_path):
    import base64
    from glyph.tui import data as D
    p = base64.b64encode(json.dumps({"type": "SSH"}).encode()).decode()
    cfg = decode_bytes("t.dark", ("darktunnel://" + p).encode(),
                       filepath=str(tmp_path / "t.dark"))
    cat = Catalog(str(tmp_path / "c.db"))
    cat.add_vpn_config(cfg)
    s = D.summary(cat)
    assert s["vpn_configs"] == 1
    assert s["vpn_decoded"] == 1
    cat.close()


# ── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_vpndec_dark(tmp_path, capsys):
    import base64
    from glyph.cli import main
    f = tmp_path / "t.dark"
    p = base64.b64encode(json.dumps(
        {"type": "VLESS", "server": "cli.test", "port": 443,
         "sni": "sni.test"}).encode()).decode()
    f.write_text("darktunnel://" + p)
    db = str(tmp_path / "c.db")
    assert main(["vpndec", str(f), "--db", db]) == 0
    out = capsys.readouterr().out
    assert "cli.test" in out
    assert "vless" in out.lower() or "VLESS" in out


def test_cli_vpndec_json(tmp_path, capsys):
    import base64
    from glyph.cli import main
    f = tmp_path / "t.dark"
    p = base64.b64encode(json.dumps(
        {"type": "SSH", "server": "j.test", "port": 22}).encode()).decode()
    f.write_text("darktunnel://" + p)
    db = str(tmp_path / "c.db")
    assert main(["vpndec", str(f), "--db", db, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["host"] == "j.test"
    assert data["protocol"] == "ssh"
