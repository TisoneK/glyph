"""Real-world integration test — language-code dictionary (proxied capture).

Fixture source: linebet.com's ``bff-api/config/group/get`` endpoint,
captured live 2026-07-30 via headless chromium routed through a geo-
permitted upstream proxy (Session 7). The proxy bypassed the geo-block
that capped the direct-egress capture at 20 flows; the proxied capture
got 189 flows / 87 endpoints, including the full 60-language dictionary
the SPA offers in its language switcher.

The fixture (``tests/fixtures/real/linebet_languages.json``) carries the
real ``{code, title}`` pairs — e.g. ``en`` -> ``English``, ``ar`` ->
``العربية``, ``cn`` -> ``汉语``. Rosetta's ``sibling_generic`` strategy
decodes these by pairing the ``code`` field with the ``title`` field in
each language object. This test asserts those decodings.

This is the deeper real-world validation Session 6's report flagged as a
follow-up: a substantive (60-entry) code->meaning dictionary recovered
from a real target, not just the contacts templateType set.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from glyph.catalog import Catalog, Flow

FIXTURE = Path(__file__).parent / "fixtures" / "real" / "linebet_languages.json"


def _load_languages_catalog() -> Catalog:
    """Build a catalog seeded with the real linebet languages payload."""
    cat = Catalog(path=":memory:")
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # Wrap the languages list under the same key Rosetta saw ($.{"-1009": [...]}).
    payload = {"-1009": data["languages"]}
    cat.add_flow(Flow(
        method="GET",
        url="https://linebet.com/bff-api/config/group/get?groups=b.core,d.core",
        host="linebet.com", path="/bff-api/config/group/get",
        query="groups=b.core,d.core",
        req_headers={}, req_body=None,
        status=200, resp_headers={},
        resp_body=json.dumps(payload),
        resp_mime="application/json",
        source="real-capture-proxied",
    ))
    return cat


@pytest.fixture(scope="module")
def decoded_languages():
    cat = _load_languages_catalog()
    from glyph.schema import infer_all
    from glyph.rosetta import build_dictionary
    infer_all(cat)
    build_dictionary(cat)
    return {(d.json_path, str(d.code)): d for d in cat.dictionary()}


# --- The known language-code -> language-name decodings a human reads in the
# linebet language switcher. Each is a real opaque code Rosetta recovered
# from the live capture by pairing `code` with `title` in the same object.

@pytest.mark.parametrize("code,expected", [
    ("en", "English"),
    ("ar", "العربية"),
    ("cn", "汉语"),
    ("es", "Español"),
    ("fr", "Français"),
    ("ge", "ქართული ენა"),  # linebet's 'ge' = Georgian (not ISO 'de' = German)
    ("pt", "Português"),
    ("ru", "Русский"),
    ("am", "አማርኛ"),     # Amharic — relevant to the Kenyan/East-African user
    ("sw", "Kiswahili"),   # Swahili — relevant to the Kenyan/East-African user
])
def test_language_code_decodes_to_native_name(decoded_languages, code, expected):
    """A linebet language code (e.g. 'en', 'ar', 'am') decodes to the
    language's native name (e.g. 'English', 'العربية', 'አማርኛ') via the
    sibling_generic strategy pairing `code` with `title`."""
    # The path Rosetta reported was $.-1009[].code in the live run; the
    # fixture reproduces that key, so the path matches.
    entry = decoded_languages.get(("$.-1009[].code", code))
    if entry is None:
        # The path may also appear without the leading $.-1009 prefix
        # depending on how the schema-inferer normalizes; check both.
        entry = decoded_languages.get(("$.code", code))
    assert entry is not None, (
        f"language code {code!r} not found in dictionary; "
        f"have keys: {list(decoded_languages.keys())[:10]}")
    assert entry.meaning == expected, (
        f"code {code!r} decoded to {entry.meaning!r}, expected {expected!r}")
    assert entry.confidence >= 0.9, (
        f"code {code!r} confidence {entry.confidence} < 0.9")


def test_languages_dictionary_is_substantial(decoded_languages):
    """The fixture has 60 languages; the dictionary should decode a large
    fraction of them (not 1-2). Confirms the pipeline ran across the whole
    list, not just the first object."""
    # Count entries whose path ends in '.code' under the languages structure.
    code_entries = [d for k, d in decoded_languages.items()
                    if k[0].endswith(".code") or k[0] == "$.code"]
    assert len(code_entries) >= 30, (
        f"only {len(code_entries)} language-code decodings; expected >= 30 "
        f"from the 60-language fixture")


def test_languages_decoded_via_sibling_generic(decoded_languages):
    """The sibling_generic strategy (code field paired with a generic label
    field `title` in the same object) is what should carry these decodings —
    same mechanism as the Session 6 contacts templateType set, now validated
    on a different (larger) real-world structure."""
    sibling = [d for d in decoded_languages.values()
               if "sibling" in d.strategy]
    assert len(sibling) >= 30, (
        f"only {len(sibling)} sibling-strategy decodings; the language codes "
        f"should decode via sibling_generic pairing code<->title")
