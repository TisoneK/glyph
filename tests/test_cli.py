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
