"""Schema inference and name-aware enum detection."""
from __future__ import annotations

from glyph.capture import ingest_har
from glyph.schema import infer_all


def _paths(catalog):
    fields = {}
    for ep in catalog.endpoints():
        for f in catalog.fields_for_endpoint(ep.id):
            fields[f.json_path] = f
    return fields


def test_status_is_enum_but_id_is_not(catalog, har_file, make_entry):
    path = har_file([make_entry(
        "GET", "https://s.t/orders",
        body='{"orders":[{"id":1,"status":3},{"id":2,"status":1}]}')])
    ingest_har(catalog, path)
    res = infer_all(catalog)
    fields = _paths(catalog)
    assert fields["$.orders[].status"].is_enum_candidate is True
    assert fields["$.orders[].id"].is_enum_candidate is False
    assert res["enum_candidates"] == 1


def test_money_and_date_fields_excluded(catalog, har_file, make_entry):
    path = har_file([make_entry(
        "GET", "https://s.t/tx",
        body='{"items":[{"amount":10,"created_at":"2026-01-01"},'
             '{"amount":20,"created_at":"2026-01-02"}]}')])
    ingest_har(catalog, path)
    infer_all(catalog)
    fields = _paths(catalog)
    assert fields["$.items[].amount"].is_enum_candidate is False
    assert fields["$.items[].created_at"].is_enum_candidate is False


def test_string_enum_detected(catalog, har_file, make_entry):
    path = har_file([make_entry(
        "GET", "https://s.t/u",
        body='{"users":[{"role":"admin"},{"role":"member"},{"role":"admin"}]}')])
    ingest_har(catalog, path)
    infer_all(catalog)
    assert _paths(catalog)["$.users[].role"].is_enum_candidate is True
