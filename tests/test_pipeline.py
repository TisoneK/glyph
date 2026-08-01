"""Parallel analysis pipeline (ADR-15).

run_analysis() runs the post-capture stages as concurrent lanes:
schema→rosetta (chained), sensitive, snihunt — each with its own
target-anchored Catalog connection. These tests prove (a) the lanes
actually overlap in time, (b) every write lands on the ACTIVE target and
never the (unassigned) bucket, and (c) the opt-out flags skip lanes.
"""
from __future__ import annotations

import json
import threading

from glyph.capture import ingest_har
from glyph.catalog import Catalog
from glyph.pipeline import run_analysis


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


def test_lanes_overlap_concurrently(tmp_path, make_entry, monkeypatch):
    """schema→rosetta, sensitive, and snihunt run at the SAME time.

    A threading.Barrier(3) proves overlap: if the lanes ran sequentially
    (one finishing before the next starts), each lane would block forever
    waiting for the others and the barrier would time out. With concurrent
    lanes, all three arrive and pass.
    """
    import glyph.rosetta as ros
    import glyph.schema as sch
    import glyph.sensitive as sens
    import glyph.snihunt as sh

    db = _seeded(tmp_path, make_entry)
    barrier = threading.Barrier(3)  # schema-lane, sensitive, snihunt

    def _blocking(*a, **kw):
        barrier.wait(timeout=10)  # all 3 lanes must be alive simultaneously
        return {}

    # Each stage entry point blocks until ALL three lanes have arrived.
    monkeypatch.setattr(sch, "infer_all", _blocking)
    monkeypatch.setattr(sens, "run_scan", _blocking)
    monkeypatch.setattr(sh, "run_hunt", _blocking)
    # rosetta runs in the same lane right after schema — return a valid
    # summary so the lane completes without touching the barrier.
    monkeypatch.setattr(ros, "build_dictionary",
                        lambda cat: {"entries": 0, "needs_review": 0,
                                     "high_confidence": 0})

    res = run_analysis(db, target="s.t")
    # Barrier passed => the three lanes overlapped in time. Shape intact.
    assert set(res) == {"sch", "ros", "sens", "sni"}
    assert res["sch"] == {} and res["sens"] == {} and res["sni"] == {}
    assert res["ros"] == {"entries": 0, "needs_review": 0,
                          "high_confidence": 0}


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

    res = run_analysis(db, target="s.t", no_snihunt=True)

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
    import glyph.snihunt as sh

    db = _seeded(tmp_path, make_entry)
    calls = {"scan": 0, "hunt": 0}
    monkeypatch.setattr(sens, "run_scan", lambda cat: calls.__setitem__("scan", calls["scan"] + 1) or {})
    monkeypatch.setattr(sh, "run_hunt",
                        lambda cat, net=True, progress=None:
                        calls.__setitem__("hunt", calls["hunt"] + 1) or {})

    res = run_analysis(db, target="s.t", no_sensitive=True, no_snihunt=True)
    assert res["sens"] is None and res["sni"] is None
    assert calls == {"scan": 0, "hunt": 0}


def test_snihunt_no_net_passes_net_false(tmp_path, make_entry, monkeypatch):
    import glyph.snihunt as sh

    db = _seeded(tmp_path, make_entry)
    nets = []
    monkeypatch.setattr(sh, "run_hunt",
                        lambda cat, net=True, progress=None:
                        nets.append(net) or {})

    res = run_analysis(db, target="s.t", snihunt_no_net=True)
    assert res["sni"] == {}
    assert nets == [False]  # local heuristics only (no DoH/CT/reverse-IP)
