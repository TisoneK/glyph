"""Rosetta: the three correlation strategies + confidence model."""
from __future__ import annotations

from glyph.capture import ingest_har
from glyph.rosetta import build_dictionary
from glyph.rosetta.confidence import REVIEW_THRESHOLD, combine
from glyph.schema import infer_all


def _decode(catalog, har_file, make_entry, entries):
    ingest_har(catalog, har_file(entries))
    infer_all(catalog)
    build_dictionary(catalog)
    return {(d.json_path, str(d.code)): d for d in catalog.dictionary()}


def test_sibling_prefix(catalog, har_file, make_entry):
    d = _decode(catalog, har_file, make_entry, [make_entry(
        "GET", "https://s.t/t",
        body='{"d":[{"status":3,"status_label":"Resolved"}]}')])
    entry = d[("$.d[].status", "3")]
    assert entry.meaning == "Resolved"
    assert entry.confidence >= 0.9 and entry.needs_review is False


def test_sibling_generic_code_label(catalog, har_file, make_entry):
    d = _decode(catalog, har_file, make_entry, [make_entry(
        "GET", "https://s.t/p",
        body='{"p":[{"type":2,"name":"Premium"}]}')])
    assert d[("$.p[].type", "2")].meaning == "Premium"


def test_dom_attribute(catalog, har_file, make_entry):
    d = _decode(catalog, har_file, make_entry, [
        make_entry("GET", "https://s.t/api", body='{"o":[{"status":3}]}'),
        make_entry("GET", "https://s.t/page", mime="text/html",
                   body="<span data-status='3'>Shipped</span>"),
    ])
    entry = d[("$.o[].status", "3")]
    assert entry.meaning == "Shipped"
    assert "dom_attr" in entry.strategy


def test_reference_join_is_scoped_to_same_domain(catalog, har_file, make_entry):
    # The Flashscore bug: a sports eventStageId must NOT resolve to a
    # consent-vendor purpose id of the same integer on a different domain.
    d = _decode(catalog, har_file, make_entry, [
        make_entry("GET", "https://cdn.cookielaw.org/consent/x.json",
                   body='{"purposes":[{"id":12,"name":"Personalised content"}]}'),
        make_entry("GET", "https://global.flashscore.ninja/feed",
                   body='{"stats":[{"eventStageId":12}]}'),
    ])
    # 12 on flashscore.ninja must not borrow cookielaw.org's meaning
    assert ("$.stats[].eventStageId", "12") not in d


def test_reference_join_same_domain_still_works(catalog, har_file, make_entry):
    # A cross-subdomain reference within one registrable domain still resolves.
    d = _decode(catalog, har_file, make_entry, [
        make_entry("GET", "https://www.betika.com/users",
                   body='{"users":[{"id":5,"name":"Alice"}]}'),
        make_entry("GET", "https://api.betika.com/comments",
                   body='{"c":[{"user_id":5}]}'),
    ])
    assert d[("$.c[].user_id", "5")].meaning == "Alice"


def test_reference_join_flags_for_review(catalog, har_file, make_entry):
    d = _decode(catalog, har_file, make_entry, [
        make_entry("GET", "https://s.t/users",
                   body='{"users":[{"id":5,"name":"Alice"}]}'),
        make_entry("GET", "https://s.t/comments",
                   body='{"c":[{"user_id":5,"body":"hi"}]}'),
    ])
    entry = d[("$.c[].user_id", "5")]
    assert entry.meaning == "Alice"
    assert entry.needs_review is True  # references are below the threshold


def test_combine_boosts_agreement():
    assert combine([0.9]) == 0.9
    assert combine([0.9, 0.75]) > 0.9
    assert combine([]) == 0.0


def test_competing_meanings_force_review(catalog, har_file, make_entry):
    # Same code, contradictory labels across objects -> low confidence.
    d = _decode(catalog, har_file, make_entry, [make_entry(
        "GET", "https://s.t/x",
        body='{"d":[{"status":1,"status_label":"Open"},'
             '{"status":1,"status_label":"Closed"}]}')])
    entry = d[("$.d[].status", "1")]
    assert entry.needs_review is True
    assert entry.confidence < REVIEW_THRESHOLD
