"""Correlation strategies — the engines that pair opaque codes to meaning.

Three domain-neutral strategies, strongest first:

1. **Sibling pairing** — within one JSON object, a code field sits next to
   a human-readable field (``{"status": 3, "status_label": "Shipped"}`` or
   the generic ``{"type": 2, "name": "Premium"}``).
2. **DOM attribute** — a rendered label carries the code in an attribute
   (``<span data-status="3">Shipped</span>``), harvested at capture time.
3. **Reference join** — a foreign-key-like field (``user_id``) resolves
   against an object elsewhere that has that id and a name.

Each strategy yields ``Candidate`` records; :mod:`glyph.rosetta.dictionary`
merges and scores them.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from glyph.catalog import Catalog
from glyph.rosetta import confidence as C

# Sibling suffixes that turn a code field into its label field.
_LABEL_SUFFIXES = (
    "label", "name", "text", "display", "displayname", "display_name",
    "desc", "description", "title", "str", "caption", "readable", "human",
)
# Bare label keys for the generic {code, label} pattern.
_GENERIC_LABELS = ("label", "name", "text", "title", "display", "description")
# Human-name fields used to resolve references.
_NAME_FIELDS = ("name", "title", "label", "username", "display_name",
                "displayname", "full_name", "fullname")


@dataclass
class Candidate:
    endpoint_id: Optional[int]
    json_path: str
    code: Any
    meaning: str
    strategy: str
    confidence: float
    evidence: str


def _norm(key: str) -> str:
    return key.lower().replace("_", "").replace("-", "")


def _walk_objects(value: Any, path: str) -> Iterable[Tuple[str, Dict[str, Any]]]:
    """Yield ``(path, obj)`` for every dict inside ``value``."""
    if isinstance(value, dict):
        yield path, value
        for k, v in value.items():
            yield from _walk_objects(v, f"{path}.{k}")
    elif isinstance(value, list):
        for item in value:
            yield from _walk_objects(item, f"{path}[]")


def _json_docs(catalog: Catalog, endpoint_id: int) -> List[Any]:
    docs = []
    for f in catalog.flows_for_endpoint(endpoint_id):
        body = f.resp_body
        if not body:
            continue
        looks_json = (f.resp_mime or "").endswith("json") or body.lstrip()[:1] in "{["
        if not looks_json:
            continue
        try:
            docs.append(json.loads(body))
        except (ValueError, TypeError):
            continue
    return docs


def _is_codeish(key: str, value: Any) -> bool:
    """A field worth decoding: a scalar code, not free text."""
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        return len(value) <= 32 and bool(value) and " " not in value
    return False


def sibling_pairs(catalog: Catalog, endpoint_id: int) -> List[Candidate]:
    """Strategy 1 — code field paired with a sibling label field."""
    out: List[Candidate] = []
    for doc in _json_docs(catalog, endpoint_id):
        for obj_path, obj in _walk_objects(doc, "$"):
            for key, value in obj.items():
                if not _is_codeish(key, value):
                    continue
                nkey = _norm(key)
                for lkey, lval in obj.items():
                    if lkey == key or not isinstance(lval, str) or not lval.strip():
                        continue
                    nlk = _norm(lkey)
                    field_path = f"{obj_path}.{key}"
                    # (a) prefix match: status -> statuslabel/statusname
                    if nlk.startswith(nkey) and nlk != nkey:
                        suffix = nlk[len(nkey):]
                        if suffix in _LABEL_SUFFIXES:
                            out.append(Candidate(
                                endpoint_id, field_path, value, lval.strip(),
                                "sibling_prefix", C.SIBLING_PREFIX,
                                f"'{key}'={value!r} paired with sibling "
                                f"'{lkey}'={lval!r} in {obj_path}",
                            ))
                            continue
                    # (b) generic {code, label}: only for enum-ish code keys
                    if lkey.lower() in _GENERIC_LABELS and _enum_ish(key):
                        out.append(Candidate(
                            endpoint_id, field_path, value, lval.strip(),
                            "sibling_generic", C.SIBLING_GENERIC,
                            f"'{key}'={value!r} paired with generic label "
                            f"'{lkey}'={lval!r} in {obj_path}",
                        ))
    return out


_ENUM_KEY = re.compile(
    r"(status|state|type|kind|category|role|level|tier|code|flag|mode|"
    r"stage|phase|priority|severity|gender|currency|country|lang|size|"
    r"visibility|reason|result|action|event|class|group|plan|method)",
    re.IGNORECASE,
)


def _enum_ish(key: str) -> bool:
    return bool(_ENUM_KEY.search(key))


def dom_attribute(catalog: Catalog) -> List[Candidate]:
    """Strategy 2 — a rendered label carries the code in an attribute.

    Maps catalog-wide: each page label's attribute values are matched
    against enum-candidate code values. When the attribute name echoes the
    field leaf (``data-status`` vs ``status``) confidence is higher.
    """
    enum_fields = catalog.enum_candidates()
    if not enum_fields:
        return []
    pages = catalog.pages()
    if not pages:
        return []

    # index: code value (as str) -> list of (label_text, attr_name)
    value_index: Dict[str, List[Tuple[str, str]]] = {}
    for page in pages:
        for lab in page.labels:
            text = lab.get("text")
            if not text:
                continue
            for attr_name, attr_val in (lab.get("attrs") or {}).items():
                for token in _attr_tokens(attr_val):
                    value_index.setdefault(token, []).append((text, attr_name))

    out: List[Candidate] = []
    for field in enum_fields:
        leaf = field.json_path.rstrip("[]").split(".")[-1]
        for code in field.sample_values:
            hits = value_index.get(str(code))
            if not hits:
                continue
            for label_text, attr_name in hits:
                matches_name = _norm(leaf) in _norm(attr_name) or \
                    _norm(attr_name).endswith(_norm(leaf))
                conf = C.DOM_ATTR_MATCH if matches_name else C.DOM_ATTR_GENERIC
                out.append(Candidate(
                    field.endpoint_id, field.json_path, code, label_text,
                    "dom_attr", conf,
                    f"code {code!r} found in DOM attribute '{attr_name}' on "
                    f"label {label_text!r}",
                ))
    return out


def _attr_tokens(attr_val: str) -> List[str]:
    """Split an attribute value into code-like tokens (handles class lists)."""
    return [t for t in re.split(r"[\s]+", attr_val.strip()) if t]


def reference_join(catalog: Catalog) -> List[Candidate]:
    """Strategy 3 — resolve ``*_id`` fields against named objects elsewhere."""
    # Build an id -> (name, source_path) index from all named objects.
    index: Dict[str, List[Tuple[str, str]]] = {}
    endpoints = {e.id: e for e in catalog.endpoints()}
    for ep_id in list(endpoints):
        if ep_id is None:
            continue
        for doc in _json_docs(catalog, ep_id):
            for obj_path, obj in _walk_objects(doc, "$"):
                if "id" not in obj:
                    continue
                name = next((obj[n] for n in _NAME_FIELDS
                             if isinstance(obj.get(n), str) and obj.get(n).strip()),
                            None)
                if name is None:
                    continue
                src = endpoints[ep_id].path_template if ep_id in endpoints else ""
                index.setdefault(str(obj["id"]), []).append((name, src))

    if not index:
        return []

    out: List[Candidate] = []
    for ep_id in list(endpoints):
        if ep_id is None:
            continue
        for doc in _json_docs(catalog, ep_id):
            for obj_path, obj in _walk_objects(doc, "$"):
                for key, value in obj.items():
                    kl = key.lower()
                    if not (kl.endswith("_id") or kl.endswith("id")) or kl == "id":
                        continue
                    base = re.sub(r"_?id$", "", kl)
                    hits = index.get(str(value))
                    if not hits:
                        continue
                    hinted = [h for h in hits if base and base in h[1].lower()]
                    chosen = hinted[0] if hinted else hits[0]
                    conf = C.REFERENCE_HINTED if hinted else C.REFERENCE_BARE
                    out.append(Candidate(
                        ep_id, f"{obj_path}.{key}", value, chosen[0],
                        "reference", conf,
                        f"'{key}'={value!r} resolves to object id {value!r} "
                        f"named {chosen[0]!r}"
                        + (f" (from {chosen[1]})" if chosen[1] else ""),
                    ))
    return out
