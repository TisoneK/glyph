#!/usr/bin/env python3
"""Extract a minimal real-world fixture from the live linebet capture.

Pulls the networks[]/phones[]/emails[] arrays from the captured
bff-api/config/group/get payload — the structures that carry the
templateType + templateCode + labelKey fields Rosetta decoded.

Redacts actual contact values (phone numbers, email addresses, social
handles) to placeholders — the fixture is for validating the DECODER,
not for shipping the site's published contact list. The code->label
structure (the part Rosetta decodes) is preserved verbatim.
"""
import json, sqlite3, pathlib, re

con = sqlite3.connect("scripts/capture-out/catalog.db")
row = con.execute(
    "select resp_body from flows where url like '%/bff-api/config/group/get%'"
).fetchone()
if not row:
    raise SystemExit("config/group/get flow not found")
doc = json.loads(row[0])

# The structure lives under a numeric key (-1020) in the config; pull
# networks/phones/emails wherever they appear.
fixture = {"_source": "linebet.com /bff-api/config/group/get (live capture 2026-07-30)",
           "_note": "Real templateType/templateCode/labelKey structures. Contact values redacted to placeholders."}

def find_arrays(v, path="$"):
    if isinstance(v, dict):
        for k, vv in v.items():
            if k in ("networks", "phones", "emails") and isinstance(vv, list):
                fixture[k] = vv
            else:
                find_arrays(vv, f"{path}.{k}")
    elif isinstance(v, list):
        for i, vv in enumerate(v):
            find_arrays(vv, f"{path}[{i}]")
find_arrays(doc)

# Redact actual contact values; keep the code/label-key structure.
phone_re = re.compile(r"\+?\d[\d\s\-()]{6,}")
email_re = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
for arr_name in ("networks", "phones", "emails"):
    if arr_name not in fixture:
        continue
    for item in fixture[arr_name]:
        for k in list(item.keys()):
            v = item[k]
            if isinstance(v, str):
                if email_re.search(v):
                    item[k] = "REDACTED@example.com"
                elif phone_re.fullmatch(v.strip()):
                    item[k] = "+000-0000"
                elif v.startswith(("https://", "http://")) and any(s in v for s in ("facebook", "instagram", "twitter", "t.me", "telegram")):
                    item[k] = "REDACTED_SOCIAL_URL"
                elif "linebet" in v.lower() and k in ("value", "labelKey"):
                    item[k] = "REDACTED_HANDLE"

out = pathlib.Path("tests/fixtures/real/linebet_contacts.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(fixture, indent=2, ensure_ascii=False))
print(f"wrote {out} ({out.stat().st_size} bytes)")
print(f"networks: {len(fixture.get('networks', []))} items")
print(f"phones:   {len(fixture.get('phones', []))} items")
print(f"emails:   {len(fixture.get('emails', []))} items")
print()
print("=== sample structure (networks[0]) ===")
print(json.dumps(fixture["networks"][0], indent=2))
