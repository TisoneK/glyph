"""Parallel analysis pipeline with a separate SNI lifecycle.

run_analysis() runs schema→rosetta (chained) and sensitive concurrently;
run_snihunt() owns the independent, target-pinned SNI lifecycle. These tests
prove overlap, target anchoring, and independent opt-outs.
"""
from __future__ import annotations

import json
import threading

from glyph.capture import ingest_har
from glyph.catalog import Catalog
from glyph.pipeline import run_analysis, run_pipeline, run_snihunt


def _har(tmp_path, make_entry):
    path = tmp_path / "s.har"
    path.write_text(json.dumps({"log": {"entries": [
        make_entry("GET", "https://s.t/v1/o",
                   body='{"o":[{"status":3,"status_label":"Shipped"}],'
                        '"user":{"email":"a@shop.ke"}}'),
    ]}}))
    return str(path)


def _seeded(tmp_path, make_entry):
    """A catalog with a target set + one captured flow (as `run` does)."""
    db = str(tmp_path / "c.db")
    cat = Catalog(db)
    try:
        ingest_har(cat, _har(tmp_path, make_entry))  # infers + activates s.t
    finally:
        cat.close()
    return db


def test_core_lanes_overlap_without_snihunt(tmp_path, make_entry, monkeypatch):
    """Schema/Rosetta and sensitive overlap; SNI is not in this pool."""
    import glyph.rosetta as ros
    import glyph.schema as sch
    import glyph.sensitive as sens

    db = _seeded(tmp_path, make_entry)
    barrier = threading.Barrier(2)  # schema-lane + sensitive

    def _blocking(*a, **kw):
        barrier.wait(timeout=10)
        return {}

    monkeypatch.setattr(sch, "infer_all", _blocking)
    monkeypatch.setattr(sens, "run_scan", _blocking)
    monkeypatch.setattr(ros, "build_dictionary",
                        lambda cat: {"entries": 0, "needs_review": 0,
                                     "high_confidence": 0})

    res = run_analysis(db, target="s.t")
    assert set(res) == {"sch", "ros", "sens", "sni"}
    assert res["sni"] is None  # SNI is deliberately outside the core pool
    assert res["sch"] == {} and res["sens"] == {}
    assert res["ros"] == {"entries": 0, "needs_review": 0,
                          "high_confidence": 0}


def test_pipeline_runs_sni_beside_core_analysis(tmp_path, monkeypatch):
    """The coordinated pipeline overlaps the independent SNI lifecycle."""
    import glyph.pipeline as pipeline

    barrier = threading.Barrier(2)
    calls = []

    def fake_analysis(*args, **kwargs):
        calls.append("analysis")
        barrier.wait(timeout=10)
        return {"sch": {}, "ros": {}, "sens": {}, "sni": None}

    def fake_sni(*args, **kwargs):
        calls.append("sni")
        barrier.wait(timeout=10)
        return {"sni": {"persisted": 0}}

    monkeypatch.setattr(pipeline, "run_analysis", fake_analysis)
    monkeypatch.setattr(pipeline, "run_snihunt", fake_sni)

    result = run_pipeline(str(tmp_path / "unused.db"), target="s.t")

    assert set(calls) == {"analysis", "sni"}
    assert result["sni"] == {"persisted": 0}
    assert result["sch"] == {} and result["ros"] == {}


def test_snihunt_is_separate_and_target_pinned(tmp_path, make_entry, monkeypatch):
    """SNI can be awaited independently and writes to its requested target."""
    import glyph.snihunt as sh
    db = _seeded(tmp_path, make_entry)
    seen = {}

    def fake_hunt(cat, net=True, progress=None):
        seen["target"] = cat.target()
        seen["net"] = net
        return {"persisted": 0}

    monkeypatch.setattr(sh, "run_hunt", fake_hunt)
    result = run_snihunt(db, target="s.t", snihunt_no_net=True)
    assert result == {"sni": {"persisted": 0}}
    assert seen == {"target": "s.t", "net": False}


def test_writes_anchor_to_active_target(tmp_path, make_entry):
    """Regression: analysis writes land on the ACTIVE target, never the
    (unassigned) bucket. A fresh Catalog has no active target; run_analysis
    re-activates it per lane. (TUI workers previously opened fresh catalogs
    without set_target, so fields/dictionary/findings silently went to
    target_id=0 — Session 23's `glyph target show` proved it: findings 0 /
    fields 0 / dictionary 0 while the dashboard displayed them.)"""
    db = _seeded(tmp_path, make_entry)
    with Catalog(db) as cat:
        tid = cat.resolve_target("s.t")
    assert tid is not None and tid != 0

    res = run_analysis(db, target="s.t")

    cat = Catalog(db)
    try:
        for tbl, expect in (("fields", res["sch"]["fields"]),
                            ("dictionary", res["ros"]["entries"]),
                            ("findings", res["sens"]["total"])):
            on_target = cat.conn.execute(
                f"SELECT COUNT(*) AS n FROM {tbl} WHERE target_id = ?",
                (tid,)).fetchone()["n"]
            unassigned = cat.conn.execute(
                f"SELECT COUNT(*) AS n FROM {tbl} WHERE target_id = 0"
            ).fetchone()["n"]
            assert on_target >= max(expect, 1), f"{tbl} missing on target"
            assert unassigned == 0, f"{tbl} leaked into (unassigned): {unassigned}"
    finally:
        cat.close()


def test_no_sensitive_skips_scan_lane(tmp_path, make_entry, monkeypatch):
    import glyph.sensitive as sens
    db = _seeded(tmp_path, make_entry)
    calls = {"scan": 0}

    def fake_scan(cat):
        calls["scan"] += 1
        return {}

    monkeypatch.setattr(sens, "run_scan", fake_scan)

    res = run_analysis(db, target="s.t", no_sensitive=True)
    assert res["sens"] is None
    assert calls == {"scan": 0}


def test_snihunt_no_net_passes_net_false(tmp_path, make_entry, monkeypatch):
    import glyph.snihunt as sh
    db = _seeded(tmp_path, make_entry)
    nets = []
    monkeypatch.setattr(sh, "run_hunt",
                        lambda cat, net=True, progress=None:
                        nets.append(net) or {})

    res = run_snihunt(db, target="s.t", snihunt_no_net=True)
    assert res["sni"] == {}
    assert nets == [False]  # local heuristics only (no DoH/CT/reverse-IP)


def test_no_schema_and_no_rosetta_skip_lane_stages(tmp_path, make_entry, monkeypatch):
    """Session 27: each stage of the schema->rosetta lane can be opted out
    independently (the TUI checkboxes), without touching the other lanes.
    A skipped stage leaves its result key ``None``."""
    import glyph.rosetta as ros
    import glyph.schema as sch
    import glyph.sensitive as sens
    db = _seeded(tmp_path, make_entry)

    def fake_schema(cat):
        calls["schema"] += 1
        return {}

    def fake_rosetta(cat):
        calls["rosetta"] += 1
        return {"entries": 0}  # pipeline reads ros['entries'] for progress

    def fake_scan(cat):
        calls["scan"] += 1
        return {}

    calls = {"schema": 0, "rosetta": 0, "scan": 0}
    monkeypatch.setattr(sch, "infer_all", fake_schema)
    monkeypatch.setattr(ros, "build_dictionary", fake_rosetta)
    monkeypatch.setattr(sens, "run_scan", fake_scan)
    # no_schema: rosetta still runs (over existing fields), sch is None.
    res = run_analysis(db, target="s.t", no_schema=True)
    assert res["sch"] is None and res["ros"] == {"entries": 0}
    assert calls == {"schema": 0, "rosetta": 1, "scan": 1}

    # no_rosetta: schema still runs, ros is None.
    calls = {"schema": 0, "rosetta": 0, "scan": 0}
    res = run_analysis(db, target="s.t", no_rosetta=True)
    assert res["ros"] is None and res["sch"] == {}
    assert calls == {"schema": 1, "rosetta": 0, "scan": 1}

    # both off: the whole lane is dropped, other lanes unaffected.
    calls = {"schema": 0, "rosetta": 0, "scan": 0}
    res = run_analysis(db, target="s.t", no_schema=True, no_rosetta=True)
    assert res["sch"] is None and res["ros"] is None
    assert calls == {"schema": 0, "rosetta": 0, "scan": 1}
