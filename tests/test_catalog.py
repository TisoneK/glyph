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
