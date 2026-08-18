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
    from glyph.catalog import FINDING_SENSITIVE_DATA, SEV_HIGH, Catalog, Finding
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


def test_active_target_persists_across_opens(tmp_path):
    """Session 26: the active target survives across Catalog opens, so a
    display command opening a FRESH catalog shows the CURRENT target's rows
    instead of every target's. ``restore_active=True`` is the opt-in used by
    display commands; without it the legacy all-targets fallback stays."""
    from glyph.catalog import Catalog
    db = str(tmp_path / "p.db")
    cat = Catalog(db)
    try:
        t1 = cat.set_target("alpha.example")
        cat.add_flow(Flow(method="GET", url="https://alpha.example/a", host="", path=""))
        t2 = cat.set_target("beta.example")
        cat.add_flow(Flow(method="GET", url="https://beta.example/b", host="", path=""))
        assert t1 != t2
        assert cat.summary()["flows"] == 1  # active = beta
    finally:
        cat.close()

    # Legacy: a fresh Catalog without restore sees ALL targets' rows.
    cat = Catalog(db)
    try:
        assert cat.target_id() is None
        assert cat.summary()["flows"] == 2
    finally:
        cat.close()

    # Display path: restore_active picks up the LAST active target (beta).
    cat = Catalog(db, restore_active=True)
    try:
        assert cat.target_id() == t2
        assert cat.target() == "beta.example"
        assert cat.summary()["flows"] == 1
        assert {f.host for f in cat.all_flows()} == {"beta.example"}
    finally:
        cat.close()


def test_clear_and_remove_clear_persisted_active(tmp_path):
    """Session 26: clear_active_target() and remove_target() both clear the
    persisted active target, so a later restore doesn't resurrect a stale id."""
    from glyph.catalog import Catalog
    db = str(tmp_path / "c.db")

    # clear_active_target() wipes the persistence.
    cat = Catalog(db)
    try:
        cat.set_target("alpha.example")
    finally:
        cat.close()
    cat = Catalog(db)
    cat.clear_active_target()
    cat.close()
    cat = Catalog(db, restore_active=True)
    try:
        assert cat.target_id() is None
    finally:
        cat.close()

    # remove_target() wipes the persistence too.
    db2 = str(tmp_path / "r.db")
    cat = Catalog(db2)
    try:
        tid = cat.set_target("alpha.example")
    finally:
        cat.close()
    cat = Catalog(db2)
    try:
        cat.remove_target(tid)
    finally:
        cat.close()
    cat = Catalog(db2, restore_active=True)
    try:
        assert cat.target_id() is None
    finally:
        cat.close()


def test_restore_ignores_unknown_meta_id(tmp_path):
    """A persisted active_target_id pointing at a target that no longer
    exists must not crash restore — it is simply ignored."""
    from glyph.catalog import Catalog
    db = str(tmp_path / "x.db")
    cat = Catalog(db)
    cat.set_meta("active_target_id", "999999")
    cat.close()
    cat = Catalog(db, restore_active=True)
    try:
        assert cat.target_id() is None
    finally:
        cat.close()



def test_restore_never_resurrects_unassigned_bucket(tmp_path):
    """Session 26: the reserved (unassigned) bucket (id=0) can never become
    the restored 'current' target — that would filter every table to scratch
    rows. set_active_target(0) keeps working for one-shot display but does
    not persist; a forged meta '0' is cleaned up on restore."""
    from glyph.catalog import Catalog
    db = str(tmp_path / "u0.db")

    # Forged/persisted 0: restore must clear it, not filter to unassigned.
    cat = Catalog(db)
    cat.set_meta("active_target_id", "0")
    cat.close()
    cat = Catalog(db, restore_active=True)
    try:
        assert cat.target_id() is None
        assert cat.get_meta("active_target_id") is None  # cleaned up
    finally:
        cat.close()

    # set_active_target(0) works for one-shot display but does not persist
    # (the real target stays current across opens).
    cat = Catalog(db)
    cat.set_target("real.example")
    assert cat.set_active_target(0) is True
    assert cat.target_id() == 0  # in-memory: shows unassigned right now
    cat.close()
    cat = Catalog(db, restore_active=True)
    try:
        assert cat.target_id() is not None  # real target survives
        assert cat.target() == "real.example"
    finally:
        cat.close()
