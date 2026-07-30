"""Capture: HAR ingestion and HTML label harvesting."""
from __future__ import annotations

from glyph.capture import harvest_labels, ingest_har, plain_text


def test_ingest_har_counts(catalog, har_file, make_entry):
    path = har_file([
        make_entry("GET", "https://s.t/api/o", body='{"status":3}'),
        make_entry("GET", "https://s.t/page", mime="text/html",
                   body="<span data-status='3'>Shipped</span>"),
    ])
    res = ingest_har(catalog, path)
    assert res["flows"] == 2
    assert res["pages"] == 1


def test_harvest_labels_keeps_attrs():
    labels = harvest_labels(
        "<div><span data-status='3' class='b'>Shipped</span>"
        "<span data-status='1'>Pending</span></div>")
    texts = {l["text"]: l["attrs"] for l in labels}
    assert texts["Shipped"]["data-status"] == "3"
    assert texts["Pending"]["data-status"] == "1"


def test_harvest_skips_script_style():
    labels = harvest_labels(
        "<p>Visible</p><script>var x='Hidden'</script>"
        "<style>.a{color:red}</style>")
    assert any(l["text"] == "Visible" for l in labels)
    assert not any("Hidden" in l["text"] for l in labels)


def test_plain_text():
    assert "Hello" in plain_text("<p>Hello</p><b>world</b>")


def test_malformed_html_does_not_crash():
    assert harvest_labels("<div><span>oops") is not None
