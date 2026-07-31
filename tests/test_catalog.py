"""Catalog store: normalization, dedup, and round-trips."""
from __future__ import annotations

from glyph.catalog import Catalog, Flow
from glyph.catalog.normalize import split_url, template_path


def test_template_path_collapses_ids():
    assert template_path("/users/123/orders") == "/users/{id}/orders"
    assert template_path("/u/550e8400-e29b-41d4-a716-446655440000") == "/u/{uuid}"
    assert template_path("/x/deadbeefdeadbeef") == "/x/{hash}"
    assert template_path("/api/orders") == "/api/orders"  # words untouched


def test_split_url_host_path_query():
    host, path, query = split_url("https://api.x.com:8443/v1/o?page=2&q=hi")
    assert host == "api.x.com:8443"
    assert path == "/v1/o"
    assert query == {"page": "2", "q": "hi"}


def test_flows_collapse_onto_one_endpoint(catalog: Catalog):
    catalog.add_flow(Flow(method="get", url="https://a.b/users/1", host="", path=""))
    catalog.add_flow(Flow(method="GET", url="https://a.b/users/2", host="", path=""))
    endpoints = catalog.endpoints()
    assert len(endpoints) == 1
    assert endpoints[0].key == "GET a.b/users/{id}"
    assert catalog.summary()["flows"] == 2


def test_reachability_is_neutral_attribute(catalog: Catalog):
    catalog.add_flow(Flow(method="GET", url="https://a.b/x", host="", path=""))
    ep = catalog.endpoints()[0]
    assert ep.reachability == "direct"
    catalog.set_reachability(ep.id, "needs_tunnel", "residential IP required")
    assert catalog.endpoints()[0].reachability == "needs_tunnel"


def test_multi_target_coexists_and_clears_per_target(tmp_path):
    """ADR-12: multiple targets coexist; clear_target wipes only one."""
    from glyph.catalog import Catalog, Finding, FINDING_SENSITIVE_DATA, SEV_HIGH
    from glyph.catalog.models import PageObservation
    cat = Catalog(str(tmp_path / "mt.db"))
    try:
        t1 = cat.set_target("alpha.example")
        t2 = cat.set_target("beta.example")
        assert t1 != t2

        # Writes stamp the active target (t2).
        cat.add_flow(Flow(method="GET", url="https://beta.example/x", host="", path=""))
        assert cat.summary()["flows"] == 1

        # Switch to t1, write, clear_target on t1 must NOT touch t2.
        cat.set_active_target(t1)
        cat.add_flow(Flow(method="GET", url="https://alpha.example/y", host="", path=""))
        cat.add_flow(Flow(method="GET", url="https://alpha.example/z", host="", path=""))
        assert cat.summary()["flows"] == 2
        cat.set_active_target(t2)
        assert cat.summary()["flows"] == 1, "t2 survived t1's writes"
        assert cat.summary(all_targets=True)["flows"] == 3

        # Re-run t1: clear_target replaces its rows only.
        cat.set_active_target(t1)
        cat.clear_target()
        assert cat.summary()["flows"] == 0
        cat.set_active_target(t2)
        assert cat.summary()["flows"] == 1, "t2 survived t1's clear"

        # Findings + pages are per-target too.
        cat.set_target("gamma.example")
        cat.add_finding(Finding(kind=FINDING_SENSITIVE_DATA, category="email",
                                severity=SEV_HIGH, location="$.x",
                                evidence="e", value_sample="a@b.com"))
        cat.add_page(PageObservation(url="https://gamma.example/"))
        assert len(cat.findings()) == 1
        assert len(cat.pages()) == 1
        cat.set_target("delta.example")
        assert len(cat.findings()) == 0, "findings filtered to active target"
        assert len(cat.pages()) == 0
        assert len(cat.findings(all_targets=True)) == 1

        # targets() lists real targets + the reserved unassigned bucket.
        hosts = {t["host"] for t in cat.targets()}
        assert {"alpha.example", "beta.example", "gamma.example",
                "delta.example", "(unassigned)"} <= hosts

        # remove_target deletes the target AND its rows.
        cat.remove_target(t2)
        remaining = {t["host"] for t in cat.targets()}
        assert "beta.example" not in remaining
        cat.clear_active_target()
        # t2's flow is gone; the other targets' rows are intact.
        all_flows = cat.all_flows(all_targets=True)
        assert not any(f.host == "beta.example" for f in all_flows)
    finally:
        cat.close()


def test_unassigned_target_dedupes_upserts(tmp_path):
    """Rows written with no active target land in the unassigned bucket
    (id=0) and still dedup under the new UNIQUEs (NULL != NULL in SQLite
    would break this without the sentinel)."""
    from glyph.catalog import Catalog
    cat = Catalog(str(tmp_path / "u.db"))
    try:
        # No set_target call — both flows hit the same endpoint shape.
        cat.add_flow(Flow(method="get", url="https://a.b/users/1", host="", path=""))
        cat.add_flow(Flow(method="GET", url="https://a.b/users/2", host="", path=""))
        eps = cat.endpoints(all_targets=True)
        assert len(eps) == 1, eps  # collapsed onto one endpoint
        assert cat.summary(all_targets=True)["flows"] == 2
        # The unassigned target exists.
        assert any(t["host"] == "(unassigned)" for t in cat.targets())
    finally:
        cat.close()
