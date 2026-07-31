"""Output helpers — `--json` vs human rendering. Presentation only."""
from __future__ import annotations

import json
from typing import Any


def emit(data: Any, as_json: bool) -> None:
    """Print ``data`` as indented JSON, or as a human-readable tree."""
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        return
    print(human(data))


def human(data: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(data, dict):
        lines = []
        for k, v in data.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:")
                lines.append(human(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {v}")
        return "\n".join(lines)
    if isinstance(data, list):
        return "\n".join(human(item, indent) if isinstance(item, (dict, list))
                         else f"{pad}- {item}" for item in data)
    return f"{pad}{data}"
