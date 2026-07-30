"""Shared test fixtures — a tmp catalog and a HAR-file factory."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from glyph.catalog import Catalog


@pytest.fixture
def catalog(tmp_path):
    cat = Catalog(str(tmp_path / "test.db"))
    yield cat
    cat.close()


def _entry(method: str, url: str, *, status: int = 200,
           mime: str = "application/json", body: str = "{}",
           req_headers: Optional[Dict[str, str]] = None,
           resp_headers: Optional[Dict[str, str]] = None,
           req_body: Optional[str] = None) -> Dict[str, Any]:
    def hlist(h: Optional[Dict[str, str]]):
        return [{"name": k, "value": v} for k, v in (h or {}).items()]

    entry: Dict[str, Any] = {
        "request": {"method": method, "url": url, "headers": hlist(req_headers)},
        "response": {"status": status,
                     "content": {"mimeType": mime, "text": body},
                     "headers": hlist(resp_headers)},
    }
    if req_body is not None:
        entry["request"]["postData"] = {"text": req_body}
    return entry


@pytest.fixture
def har_file(tmp_path):
    """Return a factory that writes a HAR from entry dicts and returns its path."""
    counter = {"n": 0}

    def make(entries: List[Dict[str, Any]]) -> str:
        counter["n"] += 1
        path = tmp_path / f"session{counter['n']}.har"
        path.write_text(json.dumps({"log": {"entries": entries}}))
        return str(path)

    make.entry = _entry  # type: ignore[attr-defined]
    return make


@pytest.fixture
def make_entry():
    return _entry
