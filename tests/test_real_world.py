"""Real-world integration test — validates the pipeline against a REAL
captured payload (not synthetic fixtures).

Fixture source: a live capture of linebet.com's ``bff-api/config/group/get``
endpoint (2026-07-30, headless chromium via glyph.capture.driver). The
fixture carries the real ``templateType``/``templateCode``/``title``/
``labelKey`` structures from the site's contacts config — with actual
contact values (phone numbers, email addresses, social URLs) redacted to
placeholders. The code->label structure Rosetta decodes is preserved verbatim.

This is the "kept separate from the unit suite" integration test the
backlog item asks for (``Real-world validation of the pipeline``). It
asserts that Rosetta, running on real captured data, recovers the same
code->meaning mappings a human analyst would read off the rendered page.

Per ``user/preferences.md`` (Testing): unit tests over hand-authored
inputs prove internal consistency, not that the tool works against a
messy real target. This test is the latter.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from glyph.catalog import Catalog, Flow

FIXTURE = Path(__file__).parent / "fixtures" / "real" / "linebet_contacts.json"


def _load_real_catalog() -> Catalog:
    """Build a catalog seeded with the real linebet contacts payload."""
    cat = Catalog(path=":memory:")
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # The fixture is the decoded JSON body; wrap it as a single flow so
    # the pipeline (schema infer -> Rosetta) runs against real data.
    cat.add_flow(Flow(
        method="GET",
        url="https://linebet.com/bff-api/config/group/get?groups=b.core,d.core",
        host="linebet.com", path="/bff-api/config/group/get",
        query="groups=b.core,d.core",
        req_headers={}, req_body=None,
        status=200, resp_headers={},
        resp_body=json.dumps(data),
        resp_mime="application/json",
        source="real-capture",
    ))
    return cat


@pytest.fixture(scope="module")
def decoded_real():
    """Run the full pipeline on the real fixture once; cache for the module."""
    cat = _load_real_catalog()
    from glyph.rosetta import build_dictionary
    from glyph.schema import infer_all
    infer_all(cat)
    build_dictionary(cat)
    return {(d.json_path, str(d.code)): d for d in cat.dictionary()}


# --- The known decodings a human would read off the linebet contacts page ---
# Each (json_path, code) -> meaning assertion is a real opaque code Rosetta
# recovered from the live capture. If any of these break, the pipeline
# regressed on real-world data, not just synthetic fixtures.

@pytest.mark.parametrize("code,expected", [
    ("17", "X"),
    ("14", "Facebook"),
    ("13", "Instagram"),
    ("9", "Telegram"),
])
def test_networks_templateType_decodes_to_brand_name(decoded_real, code, expected):
    """templateType (int) -> the social network's brand name (title field).

    A human sees the Facebook/Instagram/Telegram/X icons + labels on the
    contacts page; Rosetta recovered the same mapping from the API's
    templateType integer + title string sitting as siblings in each
    network object."""
    # The path appears under both $.-1020.networks[] and $.networks[]
    # (the config nests under a numeric key); check both.
    for path in ("$.networks[].templateType", "$.-1020.networks[].templateType"):
        entry = decoded_real.get((path, code))
        if entry is not None:
            assert entry.meaning == expected, (
                f"templateType={code} decoded to {entry.meaning!r}, "
                f"expected {expected!r} (path {path})")
            assert entry.confidence >= 0.9, (
                f"templateType={code} confidence {entry.confidence} < 0.9")
            assert not entry.needs_review
            return
    pytest.fail(f"templateType={code} not found in dictionary")


@pytest.mark.parametrize("code,expected", [
    ("x", "X"),
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("telegram", "Telegram"),
])
def test_networks_templateCode_decodes_to_brand_name(decoded_real, code, expected):
    """templateCode (string) -> the same brand name. Cross-validates the
    int-code decoding against the string-code decoding — both should agree."""
    for path in ("$.networks[].templateCode", "$.-1020.networks[].templateCode"):
        entry = decoded_real.get((path, code))
        if entry is not None:
            assert entry.meaning == expected
            assert entry.confidence >= 0.9
            return
    pytest.fail(f"templateCode={code!r} not found in dictionary")


@pytest.mark.parametrize("code,expected", [
    ("3", "Security department"),
    ("6", "Queries and suggestions"),
])
def test_emails_templateType_decodes_to_department(decoded_real, code, expected):
    """emails[].templateType (int) -> the department label (title field).

    A human reads 'Security department' and 'Queries and suggestions' as
    the email categories on the contacts page; Rosetta recovered the
    mapping from the API's templateType + title siblings."""
    for path in ("$.emails[].templateType", "$.-1020.emails[].templateType"):
        entry = decoded_real.get((path, code))
        if entry is not None:
            assert entry.meaning == expected
            assert entry.confidence >= 0.9
            return
    pytest.fail(f"emails templateType={code} not found in dictionary")


def test_real_dictionary_has_nontrivial_size(decoded_real):
    """The real capture should produce a substantial dictionary, not 1-2
    entries — confirms the pipeline ran across the whole payload."""
    assert len(decoded_real) >= 20, (
        f"real-world dictionary only has {len(decoded_real)} entries; "
        f"expected >= 20 from the linebet contacts payload")


def test_real_decodings_are_high_confidence(decoded_real):
    """Spot-check: every network/phone/email templateType decoding should
    be high-confidence (no review needed) — they're clean sibling pairs."""
    high_conf = [d for d in decoded_real.values()
                 if d.json_path.endswith("templateType")
                 and d.confidence >= 0.9
                 and not d.needs_review]
    assert len(high_conf) >= 8, (
        f"only {len(high_conf)} high-confidence templateType decodings; "
        f"expected >= 8 (the trimmed fixture has networks+phones+emails)")
