"""Drift: shape and meaning changes between two catalog snapshots."""
from __future__ import annotations

from glyph.capture import ingest_har
from glyph.catalog import Catalog
from glyph.drift import diff_catalogs
from glyph.rosetta import build_dictionary
from glyph.schema import infer_all


def _snapshot(path, har_file, make_entry, entries):
    cat = Catalog(path)
    ingest_har(cat, har_file(entries))
    infer_all(cat)
    build_dictionary(cat)
    cat.close()


def test_endpoint_added_and_removed(tmp_path, har_file, make_entry):
    before = str(tmp_path / "b.db")
    after = str(tmp_path / "a.db")
    _snapshot(before, har_file, make_entry,
              [make_entry("GET", "https://s.t/old")])
    _snapshot(after, har_file, make_entry,
              [make_entry("GET", "https://s.t/new")])
    report = diff_catalogs(before, after)
    assert report["has_drift"] is True
    assert "GET s.t/new" in report["endpoints"]["added"]
    assert "GET s.t/old" in report["endpoints"]["removed"]


def test_meaning_redefined_is_flagged(tmp_path, har_file, make_entry):
    before = str(tmp_path / "b.db")
    after = str(tmp_path / "a.db")
    _snapshot(before, har_file, make_entry, [make_entry(
        "GET", "https://s.t/o", body='{"d":[{"status":1,"status_label":"Open"}]}')])
    _snapshot(after, har_file, make_entry, [make_entry(
        "GET", "https://s.t/o", body='{"d":[{"status":1,"status_label":"Active"}]}')])
    report = diff_catalogs(before, after)
    redefined = report["dictionary"]["redefined"]
    assert any(r["before"] == "Open" and r["after"] == "Active" for r in redefined)


def test_no_drift_between_identical(tmp_path, har_file, make_entry):
    a = str(tmp_path / "1.db")
    b = str(tmp_path / "2.db")
    entry = [make_entry("GET", "https://s.t/o", body='{"x":1}')]
    _snapshot(a, har_file, make_entry, entry)
    _snapshot(b, har_file, make_entry, entry)
    assert diff_catalogs(a, b)["has_drift"] is False
