"""Mobile — mine endpoints and URLs out of an app package.

Static, dependency-free triage: unzip the APK/IPA and scan its bytes for
URLs and API-looking path strings. This is the CI-tractable Android entry
point (RESEARCH-DEEP-DIVE.md §7.3); deep decompilation (apktool/jadx) and
dynamic hooking (Frida) are analyst-workflow follow-ups, not part of this
static pass. IPAs work too, but decryption is out of scope here.
"""
from __future__ import annotations

import re
import zipfile
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from glyph.catalog import Catalog, Flow

_URL = re.compile(rb"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{4,}")
# API-ish path fragments that appear as bare strings in code.
_API_PATH = re.compile(rb"[\"'](/(?:api|v\d|rest|graphql|gateway)/"
                       rb"[A-Za-z0-9._/{}-]{1,80})[\"']")
_SCAN_SUFFIXES = (".dex", ".so", ".json", ".xml", ".js", ".properties",
                  ".plist", ".txt", ".cfg", ".config")


def _decode(b: bytes) -> str:
    return b.decode("utf-8", "replace")


def mine_apk(path: str, max_entry_bytes: int = 25_000_000) -> Dict[str, Any]:
    """Scan an APK/IPA for URLs and API paths. Returns discovered strings."""
    urls: set = set()
    api_paths: set = set()
    hosts: set = set()

    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            name = info.filename.lower()
            if info.file_size > max_entry_bytes:
                continue
            if not (name.endswith(_SCAN_SUFFIXES) or "/classes" in name
                    or name.endswith("classes.dex")):
                continue
            try:
                data = zf.read(info)
            except Exception:
                continue
            for m in _URL.finditer(data):
                url = _decode(m.group(0)).rstrip(".,);\"'")
                urls.add(url)
                host = urlsplit(url).hostname
                if host:
                    hosts.add(host)
            for m in _API_PATH.finditer(data):
                api_paths.add(_decode(m.group(1)))

    return {
        "urls": sorted(urls),
        "hosts": sorted(hosts),
        "api_paths": sorted(api_paths),
    }


def mine_apk_to_catalog(catalog: Catalog, path: str) -> Dict[str, Any]:
    """Mine an APK and record discovered URLs as endpoints in the catalog.

    Discovered endpoints are *statically found, not observed*: they are
    recorded with ``source="apk"`` and no response body, so later capture
    can confirm them.
    """
    found = mine_apk(path)
    added = 0
    for url in found["urls"]:
        catalog.add_flow(Flow(method="GET", url=url, host="", path="",
                              source="apk"))
        added += 1
    found["endpoints_added"] = added
    return found
