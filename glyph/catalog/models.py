"""Catalog data model — the entities every Glyph stage reads and writes.

These are plain dataclasses. The store (`glyph.catalog.store`) persists
them to SQLite; stages operate on them in memory. Keeping the model
independent of the storage layer means the SQLite -> DuckDB -> Postgres
promotion path (ADR-2) never touches stage code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# --- Reachability: a neutral, Glyph-internal observation (ADR-3). --------
# Glyph records whether a decoded endpoint was reachable and stops there.
# It hands off to nothing and names no external tool.
REACH_DIRECT = "direct"
REACH_NEEDS_TUNNEL = "needs_tunnel"
REACH_UNREACHABLE = "unreachable"

# --- Findings: sensitive data / sensitive endpoints / risk indicators. ---
# Glyph FLAGS and LOCATES; it never removes the value it found (this is a
# reverse-engineering tool — the value is the point). Severity is advisory.
FINDING_SENSITIVE_DATA = "sensitive_data"
FINDING_SENSITIVE_ENDPOINT = "sensitive_endpoint"
FINDING_RISK = "risk"

SEV_LOW = "low"
SEV_MEDIUM = "medium"
SEV_HIGH = "high"
SEV_CRITICAL = "critical"
_SEV_ORDER = {SEV_CRITICAL: 0, SEV_HIGH: 1, SEV_MEDIUM: 2, SEV_LOW: 3}


def severity_rank(sev: str) -> int:
    """Sort key — lower is more severe."""
    return _SEV_ORDER.get(sev, 99)


@dataclass
class Flow:
    """One observed request/response pair — the raw unit of capture."""

    method: str
    url: str
    host: str
    path: str
    query: Dict[str, Any] = field(default_factory=dict)
    req_headers: Dict[str, str] = field(default_factory=dict)
    req_body: Optional[str] = None
    status: Optional[int] = None
    resp_headers: Dict[str, str] = field(default_factory=dict)
    resp_body: Optional[str] = None
    resp_mime: Optional[str] = None
    started_at: Optional[str] = None  # ISO-8601 if known
    source: str = "har"  # har | mitm | playwright | ...
    id: Optional[int] = None


@dataclass
class Endpoint:
    """A normalized endpoint — method + templated path on a host.

    Many flows collapse onto one endpoint (``/users/123`` and
    ``/users/456`` both become ``GET /users/{id}``).
    """

    method: str
    host: str
    path_template: str
    reachability: str = REACH_DIRECT
    reachability_note: Optional[str] = None
    id: Optional[int] = None

    @property
    def key(self) -> str:
        return f"{self.method} {self.host}{self.path_template}"


@dataclass
class ObservedField:
    """A field seen in an endpoint's request or response payloads."""

    endpoint_id: int
    location: str  # "request" | "response"
    json_path: str  # e.g. "$.data[].status"
    json_type: str  # object|array|string|integer|number|boolean|null|mixed
    sample_values: List[Any] = field(default_factory=list)
    distinct_count: int = 0
    total_count: int = 0
    is_enum_candidate: bool = False
    id: Optional[int] = None


@dataclass
class DictionaryEntry:
    """Rosetta output — an opaque code decoded to its meaning.

    e.g. endpoint ``GET /orders``, field ``$.status``, code ``3`` -> "Shipped".
    """

    endpoint_id: Optional[int]
    json_path: str
    code: Any
    meaning: str
    confidence: float
    strategy: str  # how the mapping was derived
    evidence: str  # human-readable justification
    needs_review: bool = False
    review_state: Optional[str] = None  # None | confirmed | edited | rejected
    id: Optional[int] = None


@dataclass
class Finding:
    """A flagged observation — sensitive data, a sensitive endpoint, or a
    passive risk indicator. The matched value is KEPT in ``value_sample``
    (never redacted at rest); redaction is an opt-in export concern only.
    """

    kind: str          # FINDING_SENSITIVE_DATA | _ENDPOINT | _RISK
    category: str      # e.g. "email", "jwt", "admin_endpoint", "wildcard_cors"
    severity: str      # SEV_LOW | SEV_MEDIUM | SEV_HIGH | SEV_CRITICAL
    location: str      # where it is: json_path, "query:<k>", "header:<h>", "endpoint"
    evidence: str      # human-readable justification
    endpoint_id: Optional[int] = None
    value_sample: Optional[str] = None  # the actual matched value, kept intact
    party: Optional[str] = None  # first_party | third_party | unknown vs the target
    id: Optional[int] = None


@dataclass
class PageObservation:
    """A rendered-UI snapshot: the human-readable side of the Rosetta join.

    ``labels`` holds (context, text) pairs harvested from the DOM — the
    words a human reads off the screen that opaque API codes map to.
    """

    url: str
    html: Optional[str] = None
    text: Optional[str] = None
    labels: List[Dict[str, Any]] = field(default_factory=list)
    observed_at: Optional[str] = None
    id: Optional[int] = None
