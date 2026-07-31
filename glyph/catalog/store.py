"""The catalog store — a SQLite-backed home for every stage's output.

Per ADR-2 the catalog is a *library*, not a service: stages open a
:class:`Catalog`, read and write in-process, and close it. SQLite is the
MVP backend (stdlib, single file, zero ops); the DuckDB/Postgres
promotion path lives behind this same interface.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Iterable, List, Optional

from glyph.catalog.models import (
    DictionaryEntry,
    Endpoint,
    Finding,
    Flow,
    ObservedField,
    PageObservation,
    severity_rank,
)
from glyph.catalog.normalize import split_url, template_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint_id INTEGER,
    method TEXT NOT NULL,
    url TEXT NOT NULL,
    host TEXT NOT NULL,
    path TEXT NOT NULL,
    query TEXT,
    req_headers TEXT,
    req_body TEXT,
    status INTEGER,
    resp_headers TEXT,
    resp_body TEXT,
    resp_mime TEXT,
    started_at TEXT,
    source TEXT
);
CREATE TABLE IF NOT EXISTS endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    method TEXT NOT NULL,
    host TEXT NOT NULL,
    path_template TEXT NOT NULL,
    reachability TEXT DEFAULT 'direct',
    reachability_note TEXT,
    UNIQUE (method, host, path_template)
);
CREATE TABLE IF NOT EXISTS fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint_id INTEGER NOT NULL,
    location TEXT NOT NULL,
    json_path TEXT NOT NULL,
    json_type TEXT,
    sample_values TEXT,
    distinct_count INTEGER,
    total_count INTEGER,
    is_enum_candidate INTEGER DEFAULT 0,
    UNIQUE (endpoint_id, location, json_path)
);
CREATE TABLE IF NOT EXISTS dictionary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint_id INTEGER,
    json_path TEXT NOT NULL,
    code TEXT NOT NULL,
    meaning TEXT,
    confidence REAL,
    strategy TEXT,
    evidence TEXT,
    needs_review INTEGER DEFAULT 0,
    review_state TEXT,
    UNIQUE (endpoint_id, json_path, code)
);
CREATE TABLE IF NOT EXISTS page_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    html TEXT,
    text TEXT,
    labels TEXT,
    observed_at TEXT
);
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    location TEXT NOT NULL,
    evidence TEXT,
    endpoint_id INTEGER,
    value_sample TEXT,
    party TEXT,
    host TEXT,
    UNIQUE (kind, category, endpoint_id, location)
);
CREATE INDEX IF NOT EXISTS idx_flows_endpoint ON flows (endpoint_id);
CREATE INDEX IF NOT EXISTS idx_fields_endpoint ON fields (endpoint_id);
"""

SCHEMA_VERSION = "3"

# Human review outcomes stored in dictionary.review_state (NULL = not reviewed).
REVIEW_CONFIRMED = "confirmed"
REVIEW_EDITED = "edited"
REVIEW_REJECTED = "rejected"


def _dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: Optional[str], fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return fallback


class Catalog:
    """A SQLite-backed catalog. Usable as a context manager."""

    def __init__(self, path: str = "glyph.db"):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(_SCHEMA)
        self._migrate()
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        self.conn.commit()

    def _migrate(self) -> None:
        """Additive migrations for catalogs created by an older schema."""
        cols = {r["name"] for r in self.conn.execute(
            "PRAGMA table_info(dictionary)").fetchall()}
        if "review_state" not in cols:
            self.conn.execute("ALTER TABLE dictionary ADD COLUMN review_state TEXT")
        fcols = {r["name"] for r in self.conn.execute(
            "PRAGMA table_info(findings)").fetchall()}
        if "party" not in fcols:
            self.conn.execute("ALTER TABLE findings ADD COLUMN party TEXT")
        if "host" not in fcols:
            self.conn.execute("ALTER TABLE findings ADD COLUMN host TEXT")

    # -- lifecycle --------------------------------------------------------
    def __enter__(self) -> "Catalog":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    # -- endpoints --------------------------------------------------------
    def upsert_endpoint(self, method: str, host: str, path_template: str) -> int:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO endpoints (method, host, path_template) "
            "VALUES (?, ?, ?)",
            (method.upper(), host, path_template),
        )
        if cur.lastrowid and cur.rowcount:
            self.conn.commit()
            return cur.lastrowid
        row = self.conn.execute(
            "SELECT id FROM endpoints WHERE method=? AND host=? AND path_template=?",
            (method.upper(), host, path_template),
        ).fetchone()
        return int(row["id"])

    def set_reachability(self, endpoint_id: int, reachability: str,
                         note: Optional[str] = None) -> None:
        self.conn.execute(
            "UPDATE endpoints SET reachability=?, reachability_note=? WHERE id=?",
            (reachability, note, endpoint_id),
        )
        self.conn.commit()

    def endpoints(self) -> List[Endpoint]:
        rows = self.conn.execute(
            "SELECT * FROM endpoints ORDER BY host, path_template, method"
        ).fetchall()
        return [
            Endpoint(
                id=r["id"], method=r["method"], host=r["host"],
                path_template=r["path_template"], reachability=r["reachability"],
                reachability_note=r["reachability_note"],
            )
            for r in rows
        ]

    # -- flows ------------------------------------------------------------
    def add_flow(self, flow: Flow) -> int:
        """Persist a flow, deriving and linking its endpoint."""
        if not flow.host or not flow.path:
            host, path, query = split_url(flow.url)
            flow.host = flow.host or host
            flow.path = flow.path or path
            flow.query = flow.query or query
        endpoint_id = self.upsert_endpoint(
            flow.method, flow.host, template_path(flow.path)
        )
        cur = self.conn.execute(
            "INSERT INTO flows (endpoint_id, method, url, host, path, query, "
            "req_headers, req_body, status, resp_headers, resp_body, resp_mime, "
            "started_at, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                endpoint_id, flow.method.upper(), flow.url, flow.host, flow.path,
                _dumps(flow.query), _dumps(flow.req_headers), flow.req_body,
                flow.status, _dumps(flow.resp_headers), flow.resp_body,
                flow.resp_mime, flow.started_at, flow.source,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_flows(self, flows: Iterable[Flow]) -> int:
        count = 0
        for flow in flows:
            self.add_flow(flow)
            count += 1
        return count

    def flows_for_endpoint(self, endpoint_id: int) -> List[Flow]:
        rows = self.conn.execute(
            "SELECT * FROM flows WHERE endpoint_id=?", (endpoint_id,)
        ).fetchall()
        return [self._row_to_flow(r) for r in rows]

    def all_flows(self) -> List[Flow]:
        rows = self.conn.execute("SELECT * FROM flows").fetchall()
        return [self._row_to_flow(r) for r in rows]

    def _row_to_flow(self, r: sqlite3.Row) -> Flow:
        return Flow(
            id=r["id"], method=r["method"], url=r["url"], host=r["host"],
            path=r["path"], query=_loads(r["query"], {}),
            req_headers=_loads(r["req_headers"], {}), req_body=r["req_body"],
            status=r["status"], resp_headers=_loads(r["resp_headers"], {}),
            resp_body=r["resp_body"], resp_mime=r["resp_mime"],
            started_at=r["started_at"], source=r["source"],
        )

    # -- fields -----------------------------------------------------------
    def upsert_field(self, f: ObservedField) -> int:
        cur = self.conn.execute(
            "INSERT INTO fields (endpoint_id, location, json_path, json_type, "
            "sample_values, distinct_count, total_count, is_enum_candidate) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT (endpoint_id, location, json_path) DO UPDATE SET "
            "json_type=excluded.json_type, sample_values=excluded.sample_values, "
            "distinct_count=excluded.distinct_count, total_count=excluded.total_count, "
            "is_enum_candidate=excluded.is_enum_candidate",
            (
                f.endpoint_id, f.location, f.json_path, f.json_type,
                _dumps(f.sample_values), f.distinct_count, f.total_count,
                1 if f.is_enum_candidate else 0,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def fields_for_endpoint(self, endpoint_id: int) -> List[ObservedField]:
        rows = self.conn.execute(
            "SELECT * FROM fields WHERE endpoint_id=?", (endpoint_id,)
        ).fetchall()
        return [self._row_to_field(r) for r in rows]

    def enum_candidates(self) -> List[ObservedField]:
        rows = self.conn.execute(
            "SELECT * FROM fields WHERE is_enum_candidate=1"
        ).fetchall()
        return [self._row_to_field(r) for r in rows]

    def _row_to_field(self, r: sqlite3.Row) -> ObservedField:
        return ObservedField(
            id=r["id"], endpoint_id=r["endpoint_id"], location=r["location"],
            json_path=r["json_path"], json_type=r["json_type"],
            sample_values=_loads(r["sample_values"], []),
            distinct_count=r["distinct_count"], total_count=r["total_count"],
            is_enum_candidate=bool(r["is_enum_candidate"]),
        )

    # -- dictionary -------------------------------------------------------
    def upsert_dictionary(self, e: DictionaryEntry) -> int:
        # A re-run of Rosetta must never overwrite a human decision: the
        # WHERE clause skips the update for any row a human has reviewed.
        cur = self.conn.execute(
            "INSERT INTO dictionary (endpoint_id, json_path, code, meaning, "
            "confidence, strategy, evidence, needs_review) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT (endpoint_id, json_path, code) DO UPDATE SET "
            "meaning=excluded.meaning, confidence=excluded.confidence, "
            "strategy=excluded.strategy, evidence=excluded.evidence, "
            "needs_review=excluded.needs_review "
            "WHERE dictionary.review_state IS NULL "
            "AND excluded.confidence >= dictionary.confidence",
            (
                e.endpoint_id, e.json_path, _dumps(e.code), e.meaning,
                e.confidence, e.strategy, e.evidence, 1 if e.needs_review else 0,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def dictionary(self, needs_review: Optional[bool] = None,
                   review_state: Optional[str] = None,
                   include_rejected: bool = False) -> List[DictionaryEntry]:
        clauses: List[str] = []
        params: List[Any] = []
        if needs_review is not None:
            clauses.append("needs_review=?")
            params.append(1 if needs_review else 0)
        if review_state is not None:
            clauses.append("review_state IS ?" if review_state == "unreviewed"
                           else "review_state=?")
            params.append(None if review_state == "unreviewed" else review_state)
        elif not include_rejected:
            # Rejected mappings are wrong meanings a human killed — hide by default.
            clauses.append("(review_state IS NULL OR review_state != 'rejected')")
        sql = "SELECT * FROM dictionary"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY confidence DESC"
        rows = self.conn.execute(sql, tuple(params)).fetchall()
        return [
            DictionaryEntry(
                id=r["id"], endpoint_id=r["endpoint_id"], json_path=r["json_path"],
                code=_loads(r["code"], r["code"]), meaning=r["meaning"],
                confidence=r["confidence"], strategy=r["strategy"],
                evidence=r["evidence"], needs_review=bool(r["needs_review"]),
                review_state=r["review_state"],
            )
            for r in rows
        ]

    def review_entry(self, entry_id: int, state: str,
                     meaning: Optional[str] = None) -> bool:
        """Record a human review decision on a dictionary row.

        ``state`` is one of ``confirmed`` / ``edited`` / ``rejected``. A
        confirmed or edited row becomes ground truth (confidence 1.0, no
        longer needs review); ``meaning`` overrides the stored meaning when
        given (required in spirit for ``edited``). Returns ``False`` if no
        such row exists.
        """
        row = self.conn.execute(
            "SELECT meaning FROM dictionary WHERE id=?", (entry_id,)).fetchone()
        if row is None:
            return False
        new_meaning = meaning if meaning is not None else row["meaning"]
        confidence = 1.0 if state != REVIEW_REJECTED else 0.0
        self.conn.execute(
            "UPDATE dictionary SET review_state=?, meaning=?, confidence=?, "
            "needs_review=0 WHERE id=?",
            (state, new_meaning, confidence, entry_id),
        )
        self.conn.commit()
        return True

    # -- page observations ------------------------------------------------
    def add_page(self, page: PageObservation) -> int:
        cur = self.conn.execute(
            "INSERT INTO page_observations (url, html, text, labels, observed_at) "
            "VALUES (?,?,?,?,?)",
            (page.url, page.html, page.text, _dumps(page.labels), page.observed_at),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def pages(self) -> List[PageObservation]:
        rows = self.conn.execute("SELECT * FROM page_observations").fetchall()
        return [
            PageObservation(
                id=r["id"], url=r["url"], html=r["html"], text=r["text"],
                labels=_loads(r["labels"], []), observed_at=r["observed_at"],
            )
            for r in rows
        ]

    # -- target (the capture's primary host — anchors party classification)
    def set_target(self, host: Optional[str]) -> None:
        if not host:
            return
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('target_host', ?)",
            (host,))
        self.conn.commit()

    def target(self) -> Optional[str]:
        return self.get_meta("target_host")

    # -- generic meta -----------------------------------------------------
    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, value))
        self.conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    # -- findings ---------------------------------------------------------
    def add_finding(self, f: Finding) -> int:
        cur = self.conn.execute(
            "INSERT INTO findings (kind, category, severity, location, evidence, "
            "endpoint_id, value_sample, party, host) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT (kind, category, endpoint_id, location) DO UPDATE SET "
            "severity=excluded.severity, evidence=excluded.evidence, "
            "value_sample=excluded.value_sample, party=excluded.party, "
            "host=excluded.host",
            (f.kind, f.category, f.severity, f.location, f.evidence,
             f.endpoint_id, f.value_sample, f.party, f.host),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def findings(self, kind: Optional[str] = None,
                 min_severity: Optional[str] = None,
                 party: Optional[str] = None) -> List[Finding]:
        clauses: List[str] = []
        params: List[Any] = []
        if kind is not None:
            clauses.append("kind=?")
            params.append(kind)
        if party is not None:
            clauses.append("party=?")
            params.append(party)
        sql = "SELECT * FROM findings"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = self.conn.execute(sql, tuple(params)).fetchall()
        out = [
            Finding(
                id=r["id"], kind=r["kind"], category=r["category"],
                severity=r["severity"], location=r["location"],
                evidence=r["evidence"], endpoint_id=r["endpoint_id"],
                value_sample=r["value_sample"], party=r["party"], host=r["host"],
            )
            for r in rows
        ]
        if min_severity is not None:
            cutoff = severity_rank(min_severity)
            out = [f for f in out if severity_rank(f.severity) <= cutoff]
        out.sort(key=lambda f: (severity_rank(f.severity), f.kind, f.category))
        return out

    def clear_findings(self) -> None:
        """Drop all findings so a re-scan is idempotent."""
        self.conn.execute("DELETE FROM findings")
        self.conn.commit()

    # -- convenience ------------------------------------------------------
    def summary(self) -> Dict[str, int]:
        def count(table: str) -> int:
            return int(self.conn.execute(
                "SELECT COUNT(*) AS n FROM " + table).fetchone()["n"])

        return {
            "endpoints": count("endpoints"),
            "flows": count("flows"),
            "fields": count("fields"),
            "findings": count("findings"),
            "enum_candidates": int(self.conn.execute(
                "SELECT COUNT(*) AS n FROM fields WHERE is_enum_candidate=1"
            ).fetchone()["n"]),
            "dictionary": count("dictionary"),
            "pages": count("page_observations"),
        }
