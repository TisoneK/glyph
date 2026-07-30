"""Schema inference — per-endpoint JSON structure + enum-candidate flagging.

For every endpoint we walk all observed JSON payloads, aggregate the type
and sample values seen at each JSON path, and flag the paths that look
like enumerations (the opaque codes Rosetta then decodes). Name-aware
heuristics keep unique ids and money/date fields out of the enum set.

Uses ``genson`` for the emitted JSON Schema when the ``schema`` extra is
installed; falls back to a pure-stdlib builder otherwise.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from glyph.catalog import Catalog, ObservedField

# Leaf names that are almost never enumerations.
_DENY = re.compile(
    r"(^|_)(id|uuid|guid|key|token|secret|hash|sig|signature|nonce|"
    r"count|total|sum|amount|price|cost|qty|quantity|balance|"
    r"timestamp|time|date|_at|created|updated|expires|ttl|"
    r"lat|lng|lon|latitude|longitude|url|uri|href|email|phone|"
    r"name|title|description|message|body|content|text|slug)$",
    re.IGNORECASE,
)
# Leaf names that strongly suggest an enumeration.
_ALLOW = re.compile(
    r"(^|_)(status|state|type|kind|category|cat|role|level|tier|grade|"
    r"code|flag|mode|stage|phase|priority|severity|rank|"
    r"gender|currency|country|lang|locale|color|colour|size|"
    r"visibility|permission|scope|reason|result|action|event|"
    r"class|group|plan|method)$",
    re.IGNORECASE,
)

_MAX_SAMPLES = 50
_ENUM_MAX_DISTINCT = 16


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _walk(value: Any, path: str, acc: Dict[str, Dict[str, Any]]) -> None:
    """Accumulate ``path -> {types, values, count}`` over one document."""
    t = _json_type(value)
    node = acc.setdefault(path, {"types": set(), "values": [], "count": 0})
    node["types"].add(t)
    node["count"] += 1
    if t == "object":
        for k, v in value.items():
            _walk(v, f"{path}.{k}", acc)
    elif t == "array":
        for item in value:
            _walk(item, f"{path}[]", acc)
    else:
        if len(node["values"]) < _MAX_SAMPLES:
            node["values"].append(value)


def _leaf(path: str) -> str:
    seg = path.rstrip("[]").split(".")[-1]
    return seg.rstrip("[]")


def _is_enum_candidate(json_type: str, leaf: str,
                       distinct: int, total: int, values: List[Any]) -> bool:
    if json_type not in ("integer", "string"):
        return False
    if distinct == 0 or distinct > _ENUM_MAX_DISTINCT:
        return False
    if _DENY.search(leaf):
        return False
    if _ALLOW.search(leaf):
        return True  # the name alone is strong enough, even on one sample
    if total < 2:
        return False  # heuristics below need repeated observations
    if distinct < total:  # values repeat -> looks categorical
        return True
    if json_type == "integer" and all(
        isinstance(v, int) and 0 <= v <= 64 for v in values
    ):
        return True
    return False


def _iter_json_bodies(bodies: List[Tuple[str, Optional[str]]]):
    for mime, body in bodies:
        if not body:
            continue
        looks_json = (mime or "").endswith("json") or body.lstrip()[:1] in "{["
        if not looks_json:
            continue
        try:
            yield json.loads(body)
        except (ValueError, TypeError):
            continue


def infer_endpoint(catalog: Catalog, endpoint_id: int) -> Dict[str, Any]:
    """Infer fields + a JSON Schema for one endpoint; persist the fields."""
    flows = catalog.flows_for_endpoint(endpoint_id)
    resp_acc: Dict[str, Dict[str, Any]] = {}
    req_acc: Dict[str, Dict[str, Any]] = {}
    resp_docs: List[Any] = []
    for f in flows:
        for doc in _iter_json_bodies([(f.resp_mime, f.resp_body)]):
            _walk(doc, "$", resp_acc)
            resp_docs.append(doc)
        for doc in _iter_json_bodies([("application/json", f.req_body)]):
            _walk(doc, "$", req_acc)

    n_fields = 0
    for location, acc in (("response", resp_acc), ("request", req_acc)):
        for path, node in acc.items():
            types = node["types"] - {"null"} or node["types"]
            json_type = next(iter(types)) if len(types) == 1 else "mixed"
            values = node["values"]
            distinct = len({json.dumps(v, default=str) for v in values})
            enum = _is_enum_candidate(
                json_type, _leaf(path), distinct, len(values), values
            )
            catalog.upsert_field(ObservedField(
                endpoint_id=endpoint_id, location=location, json_path=path,
                json_type=json_type,
                sample_values=sorted({v for v in values if not isinstance(v, (dict, list))},
                                     key=lambda x: (str(type(x)), str(x)))[:_ENUM_MAX_DISTINCT],
                distinct_count=distinct, total_count=len(values),
                is_enum_candidate=enum,
            ))
            n_fields += 1

    return {"fields": n_fields, "schema": build_schema(resp_docs)}


def infer_all(catalog: Catalog) -> Dict[str, int]:
    """Infer fields for every endpoint. Returns aggregate counts."""
    total_fields = 0
    enums = 0
    for ep in catalog.endpoints():
        if ep.id is None:
            continue
        res = infer_endpoint(catalog, ep.id)
        total_fields += res["fields"]
    enums = len(catalog.enum_candidates())
    return {"endpoints": len(catalog.endpoints()),
            "fields": total_fields, "enum_candidates": enums}


def build_schema(docs: List[Any]) -> Optional[Dict[str, Any]]:
    """Build a JSON Schema from sample docs (genson if available)."""
    if not docs:
        return None
    try:
        from genson import SchemaBuilder  # optional extra
        builder = SchemaBuilder()
        for doc in docs:
            builder.add_object(doc)
        return builder.to_schema()
    except ImportError:
        return _pure_schema(docs)


def _pure_schema(docs: List[Any]) -> Dict[str, Any]:
    """Minimal stdlib JSON-Schema builder (merges sample docs)."""
    def merge(value: Any) -> Dict[str, Any]:
        t = _json_type(value)
        if t == "object":
            return {"type": "object",
                    "properties": {k: merge(v) for k, v in value.items()}}
        if t == "array":
            items = [merge(v) for v in value[:1]] or [{}]
            return {"type": "array", "items": items[0]}
        return {"type": t}

    schema = merge(docs[0])
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema
