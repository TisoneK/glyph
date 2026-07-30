"""Drift — diff two catalog snapshots taken over time.

Reports endpoints that appeared or vanished, fields whose type or enum
values changed, and dictionary meanings that were added, dropped, or
redefined. This is the Glyph layer over a structural diff: it tracks not
just shape changes but *meaning* changes (a code that started meaning
something new is exactly what breaks an integration silently).
"""
from __future__ import annotations

from typing import Any, Dict, List

from glyph.catalog import Catalog


def _endpoint_fields(cat: Catalog) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for ep in cat.endpoints():
        fields = {}
        if ep.id is not None:
            for f in cat.fields_for_endpoint(ep.id):
                fields[f"{f.location}:{f.json_path}"] = {
                    "type": f.json_type,
                    "enum": f.is_enum_candidate,
                    "values": sorted(str(v) for v in f.sample_values),
                }
        out[ep.key] = fields
    return out


def _dictionary(cat: Catalog) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for d in cat.dictionary():
        out[f"{d.endpoint_id}|{d.json_path}|{d.code}"] = d.meaning
    return out


def diff_catalogs(before_path: str, after_path: str) -> Dict[str, Any]:
    """Diff two catalog files. Returns a structured report."""
    before = Catalog(before_path)
    after = Catalog(after_path)
    try:
        return _diff(before, after)
    finally:
        before.close()
        after.close()


def _diff(before: Catalog, after: Catalog) -> Dict[str, Any]:
    b_ep = _endpoint_fields(before)
    a_ep = _endpoint_fields(after)
    b_keys, a_keys = set(b_ep), set(a_ep)

    added = sorted(a_keys - b_keys)
    removed = sorted(b_keys - a_keys)
    changed: List[Dict[str, Any]] = []
    for key in sorted(b_keys & a_keys):
        bf, af = b_ep[key], a_ep[key]
        bfk, afk = set(bf), set(af)
        field_added = sorted(afk - bfk)
        field_removed = sorted(bfk - afk)
        field_mod = []
        for fk in sorted(bfk & afk):
            if bf[fk] != af[fk]:
                field_mod.append({"field": fk, "before": bf[fk], "after": af[fk]})
        if field_added or field_removed or field_mod:
            changed.append({
                "endpoint": key,
                "fields_added": field_added,
                "fields_removed": field_removed,
                "fields_changed": field_mod,
            })

    b_dict, a_dict = _dictionary(before), _dictionary(after)
    dict_added = sorted(set(a_dict) - set(b_dict))
    dict_removed = sorted(set(b_dict) - set(a_dict))
    dict_changed = [
        {"code": k, "before": b_dict[k], "after": a_dict[k]}
        for k in sorted(set(b_dict) & set(a_dict)) if b_dict[k] != a_dict[k]
    ]

    return {
        "endpoints": {"added": added, "removed": removed, "changed": changed},
        "dictionary": {"added": dict_added, "removed": dict_removed,
                       "redefined": dict_changed},
        "has_drift": bool(added or removed or changed or dict_added
                          or dict_removed or dict_changed),
    }
