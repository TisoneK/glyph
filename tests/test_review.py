"""HITL review: persistence, queue ops, interactive loop, migration."""
from __future__ import annotations

import sqlite3

import pytest

from glyph import review as R
from glyph.capture import ingest_har
from glyph.catalog import Catalog
from glyph.rosetta import build_dictionary
from glyph.schema import infer_all


def _catalog_with_pending(catalog, har_file, make_entry):
    """A catalog whose dictionary has 2 pending (reference-join) rows."""
    ingest_har(catalog, har_file([
        make_entry("GET", "https://s.t/users",
                   body='{"users":[{"id":5,"name":"Alice"}]}'),
        make_entry("GET", "https://s.t/comments",
                   body='{"c":[{"user_id":5,"body":"hi"}]}'),
    ]))
    infer_all(catalog)
    build_dictionary(catalog)
    return catalog


def test_pending_lists_flagged_rows(catalog, har_file, make_entry):
    _catalog_with_pending(catalog, har_file, make_entry)
    rows = R.pending(catalog)
    assert len(rows) == 1
    assert rows[0].meaning == "Alice" and rows[0].needs_review is True


def test_confirm_makes_ground_truth(catalog, har_file, make_entry):
    _catalog_with_pending(catalog, har_file, make_entry)
    entry = R.pending(catalog)[0]
    assert R.confirm(catalog, entry.id) is True
    row = [e for e in catalog.dictionary() if e.id == entry.id][0]
    assert row.review_state == "confirmed"
    assert row.confidence == 1.0 and row.needs_review is False
    assert R.pending(catalog) == []


def test_edit_changes_meaning(catalog, har_file, make_entry):
    _catalog_with_pending(catalog, har_file, make_entry)
    entry = R.pending(catalog)[0]
    R.edit(catalog, entry.id, "Alice Cooper")
    row = [e for e in catalog.dictionary() if e.id == entry.id][0]
    assert row.meaning == "Alice Cooper" and row.review_state == "edited"


def test_edit_requires_meaning(catalog, har_file, make_entry):
    _catalog_with_pending(catalog, har_file, make_entry)
    entry = R.pending(catalog)[0]
    with pytest.raises(ValueError):
        R.edit(catalog, entry.id, "")


def test_reject_hides_from_dictionary(catalog, har_file, make_entry):
    _catalog_with_pending(catalog, har_file, make_entry)
    entry = R.pending(catalog)[0]
    R.reject(catalog, entry.id)
    assert all(e.id != entry.id for e in catalog.dictionary())  # hidden
    assert any(e.id == entry.id
               for e in catalog.dictionary(include_rejected=True))  # still there


def test_review_survives_rosetta_rerun(catalog, har_file, make_entry):
    _catalog_with_pending(catalog, har_file, make_entry)
    entry = R.pending(catalog)[0]
    R.edit(catalog, entry.id, "Renamed")
    build_dictionary(catalog)  # a re-run must not clobber the human decision
    row = [e for e in catalog.dictionary() if e.id == entry.id][0]
    assert row.meaning == "Renamed" and row.review_state == "edited"


def test_auto_confirm_respects_threshold(catalog, har_file, make_entry):
    _catalog_with_pending(catalog, har_file, make_entry)
    assert R.auto_confirm(catalog, 0.9) == 0   # references sit at 0.85
    assert R.auto_confirm(catalog, 0.8) == 1
    assert R.pending(catalog) == []


def test_review_missing_id_returns_false(catalog):
    assert catalog.review_entry(999, "confirmed") is False


def test_interactive_loop_records_decisions(catalog, har_file, make_entry):
    ingest_har(catalog, har_file([
        make_entry("GET", "https://s.t/users",
                   body='{"users":[{"id":5,"name":"Alice"},{"id":7,"name":"Bob"}]}'),
        make_entry("GET", "https://s.t/comments",
                   body='{"c":[{"user_id":5},{"user_id":7}]}'),
    ]))
    infer_all(catalog)
    build_dictionary(catalog)
    inputs = iter(["c", "e Robert"])  # confirm first, edit second
    actions = R.run_interactive(
        catalog, input_fn=lambda _p: next(inputs), output_fn=lambda _s: None)
    assert actions["confirmed"] == 1 and actions["edited"] == 1
    s = R.stats(catalog)
    assert s["confirmed"] == 1 and s["edited"] == 1 and s["pending"] == 0


def test_migration_adds_review_state(tmp_path):
    """A catalog created by the pre-review schema gains the column on open."""
    path = str(tmp_path / "old.db")
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE dictionary(id INTEGER PRIMARY KEY, endpoint_id INTEGER, "
        "json_path TEXT, code TEXT, meaning TEXT, confidence REAL, strategy TEXT, "
        "evidence TEXT, needs_review INTEGER, UNIQUE(endpoint_id,json_path,code));")
    con.execute("INSERT INTO dictionary(endpoint_id,json_path,code,meaning,"
                "confidence,strategy,evidence,needs_review) "
                "VALUES (1,'$.x','1','One',0.5,'s','e',1)")
    con.commit()
    con.close()

    cat = Catalog(path)
    try:
        rows = cat.dictionary(include_rejected=True)
        assert len(rows) == 1 and rows[0].review_state is None
        assert cat.review_entry(rows[0].id, "confirmed") is True
        assert cat.dictionary()[0].review_state == "confirmed"
    finally:
        cat.close()
