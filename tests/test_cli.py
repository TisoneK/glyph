"""CLI: the pipeline entrypoint returns success and produces output."""
from __future__ import annotations

import json

from glyph.cli import main


def _har(tmp_path, make_entry):
    path = tmp_path / "s.har"
    path.write_text(json.dumps({"log": {"entries": [
        make_entry("GET", "https://s.t/v1/o",
                   body='{"o":[{"status":3,"status_label":"Shipped"}]}'),
    ]}}))
    return str(path)


def test_run_pipeline(tmp_path, make_entry, capsys):
    db = str(tmp_path / "c.db")
    har = _har(tmp_path, make_entry)
    assert main(["run", "har", har, "--db", db, "--no-snihunt"]) == 0
    out = capsys.readouterr().out
    assert "rosetta" in out
    assert "findings" in out  # the sensitive row runs by default


def test_run_no_sensitive_skips_scan(tmp_path, make_entry, capsys):
    db = str(tmp_path / "c.db")
    har = _har(tmp_path, make_entry)
    assert main(["run", "har", har, "--db", db, "--no-sensitive",
                 "--no-snihunt"]) == 0
    out = capsys.readouterr().out
    assert "rosetta" in out
    assert "findings" not in out  # the sensitive row is absent


def test_dict_after_run(tmp_path, make_entry, capsys):
    db = str(tmp_path / "c.db")
    har = _har(tmp_path, make_entry)
    main(["run", "har", har, "--db", db, "--no-snihunt"])
    capsys.readouterr()
    assert main(["dict", "--db", db]) == 0
    assert "Shipped" in capsys.readouterr().out


def test_codegen_json_to_file(tmp_path, make_entry, capsys):
    db = str(tmp_path / "c.db")
    out = str(tmp_path / "openapi.json")
    main(["run", "har", _har(tmp_path, make_entry), "--db", db, "--no-snihunt"])
    capsys.readouterr()
    assert main(["codegen", "--db", db, "--out", out]) == 0
    spec = json.loads(open(out).read())
    assert "/v1/o" in spec["paths"]


def test_run_coexists_across_targets(tmp_path, make_entry):
    # ADR-12 (multi-target): `run har` for a NEW target does NOT wipe a
    # prior target — both coexist in the catalog, each tagged with its own
    # target_id. A re-run of the SAME target replaces only that target's
    # rows (clear_target, not reset).
    import json
    from glyph.catalog import Catalog
    db = str(tmp_path / "c.db")
    first = tmp_path / "a.har"
    first.write_text(json.dumps({"log": {"entries": [
        make_entry("GET", "https://old.example/api/x")]}}))
    second = tmp_path / "b.har"
    second.write_text(json.dumps({"log": {"entries": [
        make_entry("GET", "https://new.example/api/y")]}}))
    main(["run", "har", str(first), "--db", db, "--no-snihunt"])
    main(["run", "har", str(second), "--db", db, "--no-snihunt"])
    cat = Catalog(db)
    try:
        # Both targets' hosts are present — multi-target coexistence.
        all_hosts = {e.host for e in cat.endpoints(all_targets=True)}
        assert all_hosts == {"old.example", "new.example"}, all_hosts
        # Two real targets registered (plus the reserved unassigned bucket).
        real = [t for t in cat.targets() if t["host"] != "(unassigned)"]
        assert {t["host"] for t in real} == {"old.example", "new.example"}
        # A re-run of the FIRST har replaces only old.example's rows —
        # new.example's rows survive untouched.
        main(["run", "har", str(first), "--db", db, "--no-snihunt"])
        hosts_after_rerun = {e.host for e in cat.endpoints(all_targets=True)}
        assert hosts_after_rerun == {"old.example", "new.example"}, hosts_after_rerun
        # And old.example still has exactly one endpoint (the re-run replaced,
        # not appended).
        old_eps = [e for e in cat.endpoints(all_targets=True)
                   if e.host == "old.example"]
        assert len(old_eps) == 1, old_eps
    finally:
        cat.close()


def test_missing_file_reports_error(tmp_path, capsys):
    rc = main(["capture", "har", str(tmp_path / "nope.har"),
               "--db", str(tmp_path / "c.db")])
    assert rc == 1
    assert "error" in capsys.readouterr().err


def test_by_type_aggregates_request_and_response_sides():
    """The driver tags response-side flows `playwright:<type>` and request-side
    flows `playwright:request:<type>`. by_type() must SUM both sides per type,
    not print each source key separately (the old split-on-colon behavior
    reported every type twice, e.g. document=3 + document=3)."""
    from glyph.cli._shared import by_type
    res = {"by_source": {
        "playwright:document": 3,
        "playwright:request:document": 3,
        "playwright:script": 2,
        "playwright:request:script": 4,
        "har:xhr": 1,  # no `request:` prefix — must stay its own type
    }}
    assert by_type(res) == {"document": 6, "script": 6, "xhr": 1}


def test_report_live_prints_aggregated_types(capsys):
    """`glyph capture live`'s by-type line shows each type ONCE with the
    summed count (was: every type duplicated — request side + response side)."""
    from glyph.cli._shared import report_live
    report_live("https://example.com", {
        "flows": 12, "labels": 5,
        "by_source": {"playwright:document": 3, "playwright:request:document": 3,
                       "playwright:script": 2, "playwright:request:script": 4},
        "error": None,
    })
    out = capsys.readouterr().out
    assert "by type: document=6, script=6" in out
    # The duplicated pattern is gone — document must appear exactly once.
    assert out.count("document=") == 1


def _run_with_pending(tmp_path, make_entry):
    """Build a catalog file with a pending reference-join row; return its path."""
    import json
    from glyph.capture import ingest_har
    from glyph.catalog import Catalog
    from glyph.rosetta import build_dictionary
    from glyph.schema import infer_all
    db = str(tmp_path / "c.db")
    har = tmp_path / "s.har"
    har.write_text(json.dumps({"log": {"entries": [
        make_entry("GET", "https://s.t/users",
                   body='{"users":[{"id":5,"name":"Alice"}]}'),
        make_entry("GET", "https://s.t/comments",
                   body='{"c":[{"user_id":5}]}'),
    ]}}))
    cat = Catalog(db)
    ingest_har(cat, str(har))
    infer_all(cat)
    build_dictionary(cat)
    pending_id = cat.dictionary(needs_review=True)[0].id
    cat.close()
    return db, pending_id


def test_review_single_entry_reject(tmp_path, make_entry, capsys):
    db, pid = _run_with_pending(tmp_path, make_entry)
    assert main(["review", "--db", db, "--id", str(pid), "--reject"]) == 0
    assert "rejected" in capsys.readouterr().out


def test_review_bad_id_errors(tmp_path, make_entry, capsys):
    db, _ = _run_with_pending(tmp_path, make_entry)
    assert main(["review", "--db", db, "--id", "9999", "--reject"]) == 1
    assert "error" in capsys.readouterr().err


def test_review_stats_json(tmp_path, make_entry, capsys):
    db, _ = _run_with_pending(tmp_path, make_entry)
    assert main(["review", "--db", db, "--stats", "--json"]) == 0
    assert "pending" in capsys.readouterr().out
