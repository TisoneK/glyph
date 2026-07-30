"""Codegen: OpenAPI emission with decoded-meaning annotations."""
from __future__ import annotations

from glyph.capture import ingest_har
from glyph.codegen import to_openapi
from glyph.rosetta import build_dictionary
from glyph.schema import infer_all


def test_openapi_structure_and_dictionary(catalog, har_file, make_entry):
    ingest_har(catalog, har_file([make_entry(
        "GET", "https://s.t/v1/orders",
        body='{"o":[{"status":3,"status_label":"Shipped"}]}')]))
    infer_all(catalog)
    build_dictionary(catalog)

    spec = to_openapi(catalog)
    assert spec["openapi"].startswith("3.")
    assert spec["servers"] == [{"url": "https://s.t"}]
    op = spec["paths"]["/v1/orders"]["get"]
    assert "200" in op["responses"]
    decoded = op["x-glyph-dictionary"]["$.o[].status"]["3"]
    assert decoded["meaning"] == "Shipped"


def test_reachability_annotation(catalog, har_file, make_entry):
    ingest_har(catalog, har_file([make_entry("GET", "https://s.t/x")]))
    ep = catalog.endpoints()[0]
    catalog.set_reachability(ep.id, "unreachable")
    op = to_openapi(catalog)["paths"]["/x"]["get"]
    assert op["x-glyph-reachability"] == "unreachable"
