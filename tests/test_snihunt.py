"""SNI bug-host hunt: extract, CDN detect, zero-rate, CT logs, hunt, CLI (ADR-10).

All tests run FULLY OFFLINE. Network hunters take a swappable ``http_get``
callable; we inject a fake that returns canned CT / DoH / reverse-IP
responses, so the suite is hermetic and fast.
"""
from __future__ import annotations

import json

from glyph.catalog import Catalog, Flow, FINDING_SNI_BUG_HOST
from glyph.cli import main
from glyph.snihunt import run_hunt, summarize
from glyph.snihunt import cdn as cdn_mod
from glyph.snihunt import extract as extract_mod
from glyph.snihunt import zerorate as zr_mod


# -- extract ---------------------------------------------------------------
def test_extract_hosts_collects_sni_surface():
    cat = Catalog(":memory:")
    cat.add_flow(Flow(method="GET", url="https://api.shop.ke/x", host="", path=""))
    cat.add_flow(Flow(method="POST", url="https://api.shop.ke/y", host="", path=""))
    cat.add_flow(Flow(method="GET", url="https://cdn.cloudflare.com/z.js",
                      host="", path="",
                      req_headers={"CF-Connecting-IP": "104.16.1.2"}))
    hosts = {h.host: h for h in extract_mod.extract_hosts(cat)}
    assert "api.shop.ke" in hosts
    assert hosts["api.shop.ke"].flow_ids  # 2 flows
    assert "cdn.cloudflare.com" in hosts
    assert "104.16.1.2" in hosts["cdn.cloudflare.com"].captured_ips
    cat.close()


# -- CDN detection (offline, embedded ranges) ------------------------------
def test_cdn_detect_by_ip_cloudflare():
    assert cdn_mod.detect_by_ip("104.16.1.2").name == "Cloudflare"
    assert cdn_mod.detect_by_ip("172.64.0.1").name == "Cloudflare"
    # a non-CDN IP
    assert cdn_mod.detect_by_ip("8.8.8.8") is None


def test_cdn_detect_by_host_suffix_akamai():
    assert cdn_mod.detect_by_host("edge.akamaized.net").name == "Akamai"
    assert cdn_mod.detect_by_host("x.cloudfront.net").name == "CloudFront"
    assert cdn_mod.detect_by_host("example.com") is None


def test_is_frontable_cloudflare_ip():
    assert cdn_mod.is_frontable("anything.com", ips=["104.16.1.2"]) is True
    assert cdn_mod.is_frontable("anything.com", ips=["8.8.8.8"]) is False


# -- zero-rating heuristics ------------------------------------------------
def test_zero_rate_facebook_free_basics():
    assert zr_mod.is_zero_rated("0.facebook.com")
    assert zr_mod.is_zero_rated("free.facebook.com")
    assert "facebook_free_basics" in zr_mod.zero_rate_signals("0.facebook.com")


def test_zero_rate_wikipedia_zero():
    assert zr_mod.is_zero_rated("0.wikipedia.org")
    assert zr_mod.is_zero_rated("zero.m.wikipedia.org")


def test_zero_rate_rejects_non_free_host():
    assert zr_mod.is_zero_rated("api.shop.ke") is False
    assert zr_mod.is_zero_rated("www.example.com") is False


# -- a fake http_get for the network hunters -------------------------------
def _fake_http_get_factory():
    """Return an http_get callable + a dict of URL->body for inspection."""
    routes = {}

    def get(url, timeout):
        # Match by substring so query-param order doesn't matter.
        for key, body in routes.items():
            if key in url:
                if isinstance(body, Exception):
                    raise body
                return body.encode("utf-8") if isinstance(body, str) else body
        raise RuntimeError(f"no fake route for {url}")

    get.routes = routes
    return get


def _set_doh(get, host, ips):
    """Make the fake DoH return ``ips`` for ``host`` (both providers)."""
    body = json.dumps({"Status": 0, "Answer": [
        {"name": host, "type": 1 if ":" not in ip else 28, "data": ip}
        for ip in ips
    ]}).encode()
    get.routes[f"name={host}"] = body


def _set_certspotter(get, domain, subs):
    """Make the fake certspotter return ``subs`` for ``domain``.

    Each cert issuance carries its own SAN list; we model that as one
    issuance per subdomain (the certspotter ``expand=dns_names`` shape)."""
    body = json.dumps([{"dns_names": [s]} for s in subs]).encode()
    get.routes[f"domain={domain}"] = body


def _set_reverse_ip(get, ip, siblings):
    body = ("\n".join(siblings)).encode()
    get.routes[f"q={ip}"] = body


# -- hunt orchestration ----------------------------------------------------
def test_hunt_offline_local_heuristics_only():
    # No network: a captured cloudflare host should still be flagged as
    # CDN-frontable via the embedded IP ranges (when an IP is captured) and
    # zero-rating patterns via the hostname.
    cat = Catalog(":memory:")
    cat.set_target("shop.ke")
    cat.add_flow(Flow(method="GET",
                      url="https://0.facebook.com/login", host="", path="",
                      req_headers={"CF-Connecting-IP": "104.16.1.2"}))
    cat.add_flow(Flow(method="GET", url="https://api.shop.ke/x", host="", path=""))
    summary = run_hunt(cat, net=False)
    findings = cat.findings(kind=FINDING_SNI_BUG_HOST)
    assert any(f.host == "0.facebook.com" for f in findings)
    fb = [f for f in findings if f.host == "0.facebook.com"][0]
    assert fb.category == "sni_zero_rated"  # zero-rating beats CDN
    assert fb.severity == "high"  # zero-rate (30) + captured (10) + cdn (30) = 70
    # Evidence is now structured JSON (parse_evidence), not prose.
    from glyph.snihunt import parse_evidence
    ev = parse_evidence(fb.evidence)
    assert ev["zero_rating"]  # facebook_free_basics fired
    assert ev["cdn"] == "Cloudflare"  # captured IP 104.16.1.2
    assert ev["score"] == 70
    cat.close()


def test_hunt_with_mocked_network_discovers_new_hosts():
    # The point of the stage: discover NEW hosts the capture didn't hit,
    # via CT logs + reverse-IP.
    cat = Catalog(":memory:")
    cat.set_target("shop.ke")
    cat.add_flow(Flow(method="GET", url="https://www.shop.ke/", host="", path=""))
    fake = _fake_http_get_factory()
    # DoH: www.shop.ke -> 104.16.1.2 (Cloudflare)
    _set_doh(fake, "www.shop.ke", ["104.16.1.2"])
    # CT logs: shop.ke has a wildcard cert + several subdomains
    _set_certspotter(fake, "shop.ke",
                     ["shop.ke", "www.shop.ke", "api.shop.ke",
                      "m.shop.ke", "cdn.shop.ke", "admin.shop.ke",
                      "*.shop.ke"])
    # Reverse-IP on 104.16.1.2: sibling hostnames
    _set_reverse_ip(fake, "104.16.1.2",
                    ["sibling-other.com", "another-site.shop.ke",
                     "www.shop.ke"])  # www.shop.ke is the host itself

    summary = run_hunt(cat, net=True, http_get=fake)

    findings = cat.findings(kind=FINDING_SNI_BUG_HOST)
    hosts = {f.host for f in findings}
    # The captured host is a candidate...
    assert "www.shop.ke" in hosts
    # ...AND the CT-discovered subdomains are candidates (NEW hosts the
    # capture didn't hit — the whole point of the stage).
    assert "api.shop.ke" in hosts
    assert "m.shop.ke" in hosts
    # The wildcard cert signal fired. api.shop.ke wasn't captured and has no
    # DoH route (only www.shop.ke does), so it scores shared+wildcard = 25
    # (low) — still surfaced as a candidate, which is the point.
    from glyph.snihunt import parse_evidence
    api = [f for f in findings if f.host == "api.shop.ke"][0]
    ev = parse_evidence(api.evidence)
    assert ev["wildcard"] is True
    assert ev["shared_cert"] >= 5
    assert api.severity == "low"  # 25 = shared(15) + wildcard(10); no CDN/IP
    # The reverse-IP sibling is also promoted to a candidate (one level deep;
    # siblings-of-siblings aren't chased). It scores via "reverse_sourced"
    # (shares an IP with a captured host) — the fronting signal.
    assert "sibling-other.com" in hosts
    sib = [f for f in findings if f.host == "sibling-other.com"][0]
    sev = parse_evidence(sib.evidence)
    assert sev["reverse_sourced"] is True
    # reverse_sourced (10) + Cloudflare CDN via the shared IP (30) = 40 medium.
    assert sib.severity == "medium"
    assert sev["cdn"] == "Cloudflare"
    cat.close()


def test_hunt_is_idempotent():
    cat = Catalog(":memory:")
    cat.add_flow(Flow(method="GET", url="https://0.facebook.com/x", host="", path=""))
    run_hunt(cat, net=False)
    n1 = len(cat.findings(kind=FINDING_SNI_BUG_HOST))
    run_hunt(cat, net=False)  # again
    assert len(cat.findings(kind=FINDING_SNI_BUG_HOST)) == n1  # not doubled
    cat.close()


def test_hunt_does_not_wipe_sensitive_findings():
    # Re-running snihunt must clear ONLY sni_bug_host findings, leaving the
    # sensitive stage's findings intact (the catalog.clear_findings(kind=)
    # extension).
    from glyph.sensitive import run_scan
    _JWT = ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "abc123DEF456ghi789")
    cat = Catalog(":memory:")
    cat.add_flow(Flow(method="POST", url="https://a.t/api/login", host="", path="",
                      resp_mime="application/json", status=200,
                      resp_body=json.dumps({"token": _JWT})))
    run_scan(cat)
    sens_before = len(cat.findings(kind="sensitive_data"))
    assert sens_before > 0
    run_hunt(cat, net=False)
    run_hunt(cat, net=False)  # re-run
    assert len(cat.findings(kind="sensitive_data")) == sens_before  # untouched
    cat.close()


def test_sensitive_does_not_wipe_snihunt_findings():
    # The REVERSE cross-stage bug: running `glyph sensitive` AFTER
    # `glyph snihunt` must NOT wipe the SNI findings. Session 16 fix:
    # run_scan now clears only its own kinds, not all findings.
    from glyph.sensitive import run_scan
    cat = Catalog(":memory:")
    cat.add_flow(Flow(method="GET", url="https://0.facebook.com/x", host="", path=""))
    run_hunt(cat, net=False)
    sni_before = len(cat.findings(kind="sni_bug_host"))
    assert sni_before > 0
    run_scan(cat)  # sensitive re-run — must not touch sni_bug_host
    assert len(cat.findings(kind="sni_bug_host")) == sni_before  # untouched
    cat.close()


def test_sensitive_summary_excludes_snihunt_findings():
    # The sensitive summary must NOT count sni_bug_host findings in its
    # actionable_total / by_severity. Session 16 fix: summarize filters to
    # sensitive-stage kinds only.
    from glyph.sensitive import run_scan, summarize as sens_summarize
    cat = Catalog(":memory:")
    cat.add_flow(Flow(method="POST", url="https://a.t/api/login", host="", path="",
                      resp_mime="application/json", status=200,
                      resp_body=json.dumps({"email": "x@y.com"})))
    run_scan(cat)
    sens_only = sens_summarize(cat)
    run_hunt(cat, net=False)  # now SNI findings exist too
    sni_count = len(cat.findings(kind="sni_bug_host"))
    assert sni_count > 0
    # Re-summarize sensitive — the counts must NOT have grown by sni_count.
    sens_after = sens_summarize(cat)
    assert sens_after["total"] == sens_only["total"]  # unchanged
    assert sens_after["actionable_total"] == sens_only["actionable_total"]
    cat.close()


def test_snihunt_score_is_a_real_column():
    # The score is stored in a dedicated column, not parsed from the evidence
    # string (Session 16 fix). Read it directly off the Finding.
    cat = Catalog(":memory:")
    cat.add_flow(Flow(method="GET", url="https://0.facebook.com/x", host="", path=""))
    run_hunt(cat, net=False)
    f = [x for x in cat.findings(kind="sni_bug_host") if x.host == "0.facebook.com"][0]
    # Offline, no captured IP: zero-rate(30) + captured(10) = 40. CDN can't
    # fire without a resolved/captured IP. The point is score is a real int.
    assert f.score is not None and f.score == 40
    cat.close()


def test_summarize_counts():
    cat = Catalog(":memory:")
    cat.add_flow(Flow(method="GET", url="https://0.facebook.com/x", host="", path=""))
    cat.add_flow(Flow(method="GET", url="https://api.shop.ke/y", host="", path=""))
    run_hunt(cat, net=False)
    s = summarize(cat)
    assert s["total"] > 0
    assert s["target"] is None or s["target"] == ""  # no target set
    assert "by_severity" in s
    assert "by_category" in s
    cat.close()


# -- TUI data adapter ------------------------------------------------------
def test_tui_snihunt_rows(tmp_path):
    from glyph.tui import data as D
    cat = Catalog(str(tmp_path / "t.db"))
    cat.add_flow(Flow(method="GET", url="https://0.facebook.com/x", host="", path=""))
    run_hunt(cat, net=False)
    headers, rows = D.snihunt_rows(cat)
    # Compact columns: SEV / SCR / SNI HOST / STATUS / IP / CDN / TYPE / SIGNALS
    assert headers == ["SEV", "SCR", "SNI HOST", "STATUS", "IP", "CDN", "TYPE", "SIGNALS"]
    assert any("0.facebook.com" in r for r in rows)
    cat.close()


def test_tui_summary_includes_sni_count(tmp_path):
    from glyph.tui import data as D
    cat = Catalog(str(tmp_path / "t.db"))
    cat.add_flow(Flow(method="GET", url="https://0.facebook.com/x", host="", path=""))
    run_hunt(cat, net=False)
    s = D.summary(cat)
    assert s["sni_candidates"] >= 1
    cat.close()


# -- CLI -------------------------------------------------------------------
def test_cli_snihunt_no_net(tmp_path, make_entry, capsys):
    import glyph.capture  # noqa
    from glyph.capture import ingest_har
    db = str(tmp_path / "c.db")
    har = tmp_path / "s.har"
    har.write_text(json.dumps({"log": {"entries": [
        make_entry("GET", "https://0.facebook.com/x"),
    ]}}))
    cat = Catalog(db)
    ingest_har(cat, str(har))
    cat.close()
    assert main(["snihunt", "--db", db, "--no-net"]) == 0
    out = capsys.readouterr().out
    assert "0.facebook.com" in out
    assert "zero-rated" in out.lower() or "zero" in out.lower()


def test_cli_snihunt_json(tmp_path, make_entry, capsys):
    from glyph.capture import ingest_har
    db = str(tmp_path / "c.db")
    har = tmp_path / "s.har"
    har.write_text(json.dumps({"log": {"entries": [
        make_entry("GET", "https://0.facebook.com/x"),
    ]}}))
    cat = Catalog(db)
    ingest_har(cat, str(har))
    cat.close()
    assert main(["snihunt", "--db", db, "--no-net", "--json"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "summary" in data
    assert any(f["host"] == "0.facebook.com" for f in data["findings"])


def test_cli_run_has_no_snihunt_flag():
    from glyph.cli import build_parser
    args = build_parser().parse_args(["run", "har", "x.har", "--no-snihunt"])
    assert args.no_snihunt is True


def test_cli_snihunt_direct_target_no_net(tmp_path, capsys):
    # `glyph snihunt <host>` — direct target mode, no capture needed.
    # --no-net keeps it offline (no DoH/CT/reverse-IP); the zero-rating
    # heuristics + CDN suffix detection still run over the seeded host.
    from glyph.cli import main
    db = str(tmp_path / "c.db")
    # 0.facebook.com is a known zero-rated pattern → surfaces offline.
    assert main(["snihunt", "0.facebook.com", "--db", db, "--no-net"]) == 0
    out = capsys.readouterr().out
    assert "0.facebook.com" in out
    assert "zero" in out.lower()


def test_cli_snihunt_direct_target_normalizes_scheme(tmp_path, capsys):
    # A URL with scheme+path should normalize to just the host.
    from glyph.cli import main
    from glyph.catalog import Catalog
    db = str(tmp_path / "c.db")
    assert main(["snihunt", "https://www.example.com/path", "--db", db,
                 "--no-net"]) == 0
    # The catalog should have the target set to the normalized host.
    cat = Catalog(db)
    assert cat.target() == "example.com"
    cat.close()


def test_cli_snihunt_catalog_mode_still_works(tmp_path, make_entry, capsys):
    # No positional target → runs over the existing catalog (the original mode).
    from glyph.cli import main
    from glyph.capture import ingest_har
    db = str(tmp_path / "c.db")
    har = tmp_path / "s.har"
    har.write_text(json.dumps({"log": {"entries": [
        make_entry("GET", "https://0.facebook.com/x"),
    ]}}))
    cat = Catalog(db)
    ingest_har(cat, str(har))
    cat.close()
    assert main(["snihunt", "--db", db, "--no-net"]) == 0
    out = capsys.readouterr().out
    assert "0.facebook.com" in out
