"""Harvest human-readable labels out of HTML — Rosetta's UI-side input.

Dependency-free (stdlib :mod:`html.parser`). For each element carrying
direct text we record that text alongside the element's attributes, so a
node like ``<span data-status="3">Shipped</span>`` yields a label whose
attributes still hold the opaque code ``3`` — a strong pairing signal.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import Any, Dict, List

_SKIP = {"script", "style", "noscript", "template", "svg"}
# Attributes that commonly carry an opaque code next to a rendered label.
_CODE_ATTRS = ("id", "class", "value", "title")


def _interesting_attrs(attrs: List) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for name, value in attrs:
        if value is None:
            continue
        if name.startswith("data-") or name in _CODE_ATTRS:
            out[name] = value
    return out


class _LabelParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.labels: List[Dict[str, Any]] = []
        self.text_parts: List[str] = []
        self._stack: List[Dict[str, Any]] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: List) -> None:
        if tag in _SKIP:
            self._skip_depth += 1
        self._stack.append(
            {"tag": tag, "attrs": _interesting_attrs(attrs), "buf": []}
        )

    def handle_startendtag(self, tag: str, attrs: List) -> None:
        # Self-closing element: no text, nothing to harvest.
        return

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        self.text_parts.append(text)
        if self._stack:
            self._stack[-1]["buf"].append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP and self._skip_depth:
            self._skip_depth -= 1
        # Pop back to the matching start tag (tolerant of unclosed tags).
        while self._stack:
            node = self._stack.pop()
            direct = " ".join(node["buf"]).strip()
            if direct:
                self.labels.append(
                    {"text": direct, "tag": node["tag"], "attrs": node["attrs"]}
                )
            if node["tag"] == tag:
                break


def harvest_labels(html: str) -> List[Dict[str, Any]]:
    """Return a list of ``{"text", "tag", "attrs"}`` label records."""
    parser = _LabelParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # malformed HTML shouldn't crash a capture run
        pass
    # De-duplicate identical (text, attrs) pairs while preserving order.
    seen = set()
    out: List[Dict[str, Any]] = []
    for lab in parser.labels:
        key = (lab["text"], tuple(sorted(lab["attrs"].items())))
        if key in seen:
            continue
        seen.add(key)
        out.append(lab)
    return out


def plain_text(html: str) -> str:
    """Return the concatenated visible text of an HTML document."""
    parser = _LabelParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    return " ".join(parser.text_parts)
