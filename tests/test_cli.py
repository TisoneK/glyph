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
    assert main(["run", "har", har, "--db", db]) == 0
    out = capsys.readouterr().out
    assert "rosetta" in out
    assert "sensitive:" in out  # sensitive scan runs by default


def test_run_no_sensitive_skips_scan(tmp_path, make_entry, capsys):
    db = str(tmp_path / "c.db")
    har = _har(tmp_path, make_entry)
    assert main(["run", "har", har, "--db", db, "--no-sensitive"]) == 0
    out = capsys.readouterr().out
    assert "rosetta" in out
    assert "sensitive:" not in out  # the 'sensitive:' summary line is absent


def test_dict_after_run(tmp_path, make_entry, capsys):
    db = str(tmp_path / "c.db")
    har = _har(tmp_path, make_entry)
    main(["run", "har", har, "--db", db])
    capsys.readouterr()
    assert main(["dict", "--db", db]) == 0
    assert "Shipped" in capsys.readouterr().out


def test_codegen_json_to_file(tmp_path, make_entry, capsys):
    db = str(tmp_path / "c.db")
    out = str(tmp_path / "openapi.json")
    main(["run", "har", _har(tmp_path, make_entry), "--db", db])
    capsys.readouterr()
    assert main(["codegen", "--db", db, "--out", out]) == 0
    spec = json.loads(open(out).read())
    assert "/v1/o" in spec["paths"]


def test_missing_file_reports_error(tmp_path, capsys):
    rc = main(["capture", "har", str(tmp_path / "nope.har"),
               "--db", str(tmp_path / "c.db")])
    assert rc == 1
    assert "error" in capsys.readouterr().err


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
