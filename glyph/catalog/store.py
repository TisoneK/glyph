"""The catalog store — a SQLite-backed home for every stage's output.

Per ADR-2 the catalog is a *library*, not a service: stages open a
:class:`Catalog`, read and write in-process, and close it. SQLite is the
MVP backend (stdlib, single file, zero ops); the DuckDB/Postgres
promotion path lives behind this same interface.

Per ADR-12 (multi-target, 2026-07-31) the catalog is **multi-target**: a
``targets`` table holds every host ever captured, and every data row
carries a ``target_id``. A run activates one target
(:meth:`set_target`), stamps its id on every row it writes, and
:meth:`clear_target` wipes only that target's rows — so multiple targets
coexist and a re-run is idempotent without nuking the whole catalog.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
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

# VpnConfig is defined in glyph.vpndec.models, but importing it here would
# create a cycle (vpndec imports nothing from catalog at module load — it
# takes a Catalog at call time). We import it lazily inside the methods
# that need it, so `import glyph.catalog` never pulls in vpndec.
from glyph.catalog.normalize import split_url, template_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS targets (
    -- INTEGER PRIMARY KEY (no AUTOINCREMENT) so the reserved id=0
    -- "unassigned" target is insertable. Real targets get ids >= 1.
    id INTEGER PRIMARY KEY,
    host TEXT NOT NULL UNIQUE,
    label TEXT,
    notes TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
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
    target_id INTEGER,
    method TEXT NOT NULL,
    host TEXT NOT NULL,
    path_template TEXT NOT NULL,
    reachability TEXT DEFAULT 'direct',
    reachability_note TEXT,
    UNIQUE (target_id, method, host, path_template)
);
CREATE TABLE IF NOT EXISTS fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    endpoint_id INTEGER NOT NULL,
    location TEXT NOT NULL,
    json_path TEXT NOT NULL,
    json_type TEXT,
    sample_values TEXT,
    distinct_count INTEGER,
    total_count INTEGER,
    is_enum_candidate INTEGER DEFAULT 0,
    UNIQUE (target_id, endpoint_id, location, json_path)
);
CREATE TABLE IF NOT EXISTS dictionary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    endpoint_id INTEGER,
    json_path TEXT NOT NULL,
    code TEXT NOT NULL,
    meaning TEXT,
    confidence REAL,
    strategy TEXT,
    evidence TEXT,
    needs_review INTEGER DEFAULT 0,
    review_state TEXT,
    UNIQUE (target_id, endpoint_id, json_path, code)
);
CREATE TABLE IF NOT EXISTS page_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    url TEXT NOT NULL,
    html TEXT,
    text TEXT,
    labels TEXT,
    observed_at TEXT
);
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    kind TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    location TEXT NOT NULL,
    evidence TEXT,
    endpoint_id INTEGER,
    value_sample TEXT,
    party TEXT,
    host TEXT,
    score INTEGER,
    UNIQUE (target_id, kind, category, endpoint_id, location)
);
CREATE TABLE IF NOT EXISTS vpn_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    filepath TEXT NOT NULL,
    filename TEXT NOT NULL,
    format TEXT NOT NULL,
    is_encrypted INTEGER DEFAULT 0,
    decryption_status TEXT NOT NULL,
    scheme TEXT,
    confidence REAL DEFAULT 0.0,
    key_label TEXT,
    host TEXT,
    port INTEGER,
    protocol TEXT,
    ssh_server TEXT,
    ssh_port INTEGER,
    ssh_user TEXT,
    ssh_pass TEXT,
    proxy_host TEXT,
    proxy_port INTEGER,
    payload TEXT,
    sni TEXT,
    bug_host TEXT,
    dns TEXT,
    remote_dns TEXT,
    raw_data TEXT,
    errors TEXT,
    warnings TEXT,
    decoded_at TEXT,
    UNIQUE (target_id, filepath)
);
"""

# Indexes are applied AFTER migration so their target_id columns exist
# even on pre-v4 catalogs (the migration rebuild adds them).
_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_flows_endpoint ON flows (endpoint_id);
CREATE INDEX IF NOT EXISTS idx_fields_endpoint ON fields (endpoint_id);
CREATE INDEX IF NOT EXISTS idx_flows_target ON flows (target_id);
CREATE INDEX IF NOT EXISTS idx_endpoints_target ON endpoints (target_id);
CREATE INDEX IF NOT EXISTS idx_fields_target ON fields (target_id);
CREATE INDEX IF NOT EXISTS idx_dictionary_target ON dictionary (target_id);
CREATE INDEX IF NOT EXISTS idx_pages_target ON page_observations (target_id);
CREATE INDEX IF NOT EXISTS idx_findings_target ON findings (target_id);
CREATE INDEX IF NOT EXISTS idx_vpn_configs_target ON vpn_configs (target_id);
"""

SCHEMA_VERSION = "4"

# Reserved id for rows written when no target is active (ADR-12). Every data
# row carries a non-NULL target_id so UNIQUE constraints dedup correctly
# (SQLite treats NULL as distinct in UNIQUE, which would break upserts). The
# unassigned target is created at Catalog init and shows in `glyph target
# list` as "(unassigned)" — rows land here when a caller writes without
# first calling set_target (legacy tests, REPL scratch space).
_UNASSIGNED_TARGET_ID = 0
_UNASSIGNED_HOST = "(unassigned)"

# meta key persisting the last-activated target (Session 26 fix). The active
# target is per-instance state; without persistence every display command
# (glyph flows / dict / dashboard …) opens a FRESH Catalog with no active
# target and reads fall back to ALL targets' rows. set_target /
# set_active_target write this key; display commands opt into restoring it
# via Catalog(..., restore_active=True). Write paths (run/capture) stay
# pristine — they set their own target (ADR-12 unchanged).
_ACTIVE_TARGET_META = "active_target_id"

# Human review outcomes stored in dictionary.review_state (NULL = not reviewed).
REVIEW_CONFIRMED = "confirmed"
REVIEW_EDITED = "edited"
REVIEW_REJECTED = "rejected"

# Every data table that carries a target_id (ADR-12). Used by clear_target /
# reset / remove_target so adding a new table is a one-line change here.
_DATA_TABLES = (
    "flows", "endpoints", "fields", "dictionary",
    "page_observations", "findings", "vpn_configs",
)


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Catalog:
    """A SQLite-backed catalog. Usable as a context manager.

    The catalog is multi-target (ADR-12): a ``targets`` table holds every
    host ever captured, and every data row carries a ``target_id``. The
    instance tracks an "active" target (set by :meth:`set_target`); writes
    stamp it, reads filter to it by default (fall back to "all targets"
    when no target is active). :meth:`clear_target` wipes only the active
    target's rows — a re-run is idempotent without nuking other targets.
    """

    def __init__(self, path: str = "glyph.db", *,
                 restore_active: bool = False):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        # WAL + a busy timeout let the live capture thread write flows while
        # the TUI reads concurrently (Phase 2) without "database is locked".
        try:
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA busy_timeout = 5000")
        except sqlite3.Error:
            pass
        self._active_target_id: Optional[int] = None
        self.conn.executescript(_SCHEMA)  # tables only (IF NOT EXISTS)
        self._migrate()                  # rebuild pre-v4 tables to v4 shape
        self.conn.executescript(_INDEXES)  # safe now: every table has target_id
        # Ensure the reserved unassigned target exists (id=0).
        self.conn.execute(
            "INSERT OR IGNORE INTO targets (id, host, label, created_at) "
            "VALUES (?, ?, 'unassigned', ?)",
            (_UNASSIGNED_TARGET_ID, _UNASSIGNED_HOST, _now()),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        self.conn.commit()
        # Session 26: display commands (flows/dict/dashboard …) open a FRESH
        # Catalog; the active target is per-instance state, so without this
        # restore every table would show ALL targets' rows. Opt-in kwarg —
        # write paths (run/capture) set their own target and stay pristine.
        if restore_active:
            self._restore_active_target()

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
        if "score" not in fcols:
            self.conn.execute("ALTER TABLE findings ADD COLUMN score INTEGER")
        self._migrate_to_v4()

    def _migrate_to_v4(self) -> None:
        """v4 (ADR-12): multi-target. Adds the ``targets`` table, a
        ``target_id`` column on every data table, and rebuilds each table's
        UNIQUE constraint to include ``target_id`` (SQLite can't ALTER a
        UNIQUE, so the rebuild is the standard create-copy-drop-rename).

        Existing rows are ported to the reserved unassigned target
        (``target_id = 0``) so they dedup correctly under the new UNIQUEs
        (SQLite treats NULL as distinct, which would break upserts). The
        old ``meta.target_host`` is ported into a real ``targets`` row so
        pre-multi-target catalogs keep their captured host identity.

        Idempotent: each table is rebuilt ONLY if its current schema lacks
        ``target_id``. A fresh DB (this run's _SCHEMA) has target_id on
        every table, so the whole method is a no-op; a partial old DB
        (some tables old, some fresh) rebuilds only the old ones.
        """
        # Decide per-table: a catalog may have a mix (e.g. a test seeded
        # an old `dictionary` alongside a freshly-created `endpoints`).
        to_rebuild = []
        for tbl in _V4_REBUILDS:
            existing = self.conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (tbl,),
            ).fetchone()
            if not existing:
                continue  # _SCHEMA already created it (new shape)
            if "target_id" in (existing["sql"] or ""):
                continue  # already v4-shaped
            to_rebuild.append(tbl)
        if not to_rebuild:
            return  # nothing to do

        self.conn.execute("PRAGMA foreign_keys = OFF")
        try:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS targets ("
                "id INTEGER PRIMARY KEY, "
                "host TEXT NOT NULL UNIQUE, label TEXT, notes TEXT, created_at TEXT)"
            )
            for tbl in to_rebuild:
                ddl = _V4_REBUILDS[tbl]
                tmp = f"_v4_{tbl}"
                self.conn.execute(f"DROP TABLE IF EXISTS {tmp}")
                # Create the new-shape table under the temp name.
                self.conn.execute(ddl.replace(tbl, tmp, 1))
                old_cols = [r["name"] for r in self.conn.execute(
                    f"PRAGMA table_info({tbl})").fetchall()]
                # Every old column exists in the new schema (we only
                # ADDED target_id). Copy them through; target_id stays NULL
                # for now, then ported to the unassigned id below.
                col_list = ", ".join(old_cols)
                self.conn.execute(
                    f"INSERT INTO {tmp} ({col_list}) SELECT {col_list} FROM {tbl}"
                )
                self.conn.execute(f"DROP TABLE {tbl}")
                self.conn.execute(f"ALTER TABLE {tmp} RENAME TO {tbl}")
                # Port legacy NULL target_id rows to the unassigned target
                # so they dedup under the new UNIQUE (NULL != NULL in SQLite).
                self.conn.execute(
                    f"UPDATE {tbl} SET target_id = ? WHERE target_id IS NULL",
                    (_UNASSIGNED_TARGET_ID,))
            # Port the legacy single-target host into a targets row.
            old_host = self.get_meta("target_host")
            if old_host:
                self.conn.execute(
                    "INSERT OR IGNORE INTO targets (host, label, created_at) "
                    "VALUES (?, ?, ?)",
                    (old_host, "migrated", _now()),
                )
        finally:
            self.conn.execute("PRAGMA foreign_keys = ON")
        # The unassigned target (id=0) is ensured by __init__ after _migrate.
        # Indexes are also created by __init__ after _migrate returns.

    # -- lifecycle --------------------------------------------------------
    def __enter__(self) -> "Catalog":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    # -- targets (ADR-12: multi-target) ----------------------------------
    def set_target(self, host: Optional[str], *, label: Optional[str] = None,
                   notes: Optional[str] = None) -> Optional[int]:
        # Persist the id so a later fresh Catalog (display command) can
        # restore it as the current target (Session 26).
        """Register + activate a target. Returns its id (or ``None`` if
        ``host`` is falsy).

        Idempotent: re-activating an existing host does NOT clear its rows
        (call :meth:`clear_target` for that). ``label``/``notes`` update an
        existing target only when non-None. The active target is what
        every subsequent write stamps and every read filters to (by default).
        """
        if not host:
            return None
        host = host.strip().lower()
        self.conn.execute(
            "INSERT OR IGNORE INTO targets (host, label, notes, created_at) "
            "VALUES (?, ?, ?, ?)",
            (host, label, notes, _now()),
        )
        if label is not None or notes is not None:
            self.conn.execute(
                "UPDATE targets SET label=COALESCE(?, label), "
                "notes=COALESCE(?, notes) WHERE host=?",
                (label, notes, host),
            )
        row = self.conn.execute(
            "SELECT id FROM targets WHERE host=?", (host,)
        ).fetchone()
        self._active_target_id = int(row["id"]) if row else None
        # set_meta commits; nothing else is dirty at this point.
        if self._active_target_id is not None:
            self.set_meta(_ACTIVE_TARGET_META, str(self._active_target_id))
        else:
            self.conn.commit()
        return self._active_target_id

    def target(self) -> Optional[str]:
        """The active target's host, else the latest target's host (so a
        fresh ``Catalog`` opened on a multi-target DB still shows a
        sensible name in the TUI / CLI). ``None`` if the catalog has no
        targets at all."""
        tid = self._active_target_id
        if tid is not None:
            row = self.conn.execute(
                "SELECT host FROM targets WHERE id=?", (tid,)).fetchone()
            if row:
                return row["host"]
        # Fallback: the most recently created REAL target (skip the
        # reserved unassigned bucket so the TUI sub_title doesn't read
        # "(unassigned)" when a catalog has only scratch rows).
        row = self.conn.execute(
            "SELECT host FROM targets WHERE id != ? ORDER BY id DESC LIMIT 1",
            (_UNASSIGNED_TARGET_ID,),
        ).fetchone()
        return row["host"] if row else None

    def target_id(self) -> Optional[int]:
        """The active target's id (or ``None`` if no target is active)."""
        return self._active_target_id

    def set_active_target(self, target_id: Optional[int]) -> bool:
        """Switch the active target without creating one. ``None`` clears
        the active target (reads then return all targets' rows). Returns
        ``True`` if the id exists (or is ``None``)."""
        if target_id is None:
            self._active_target_id = None
            self._clear_active_meta()
            return True
        row = self.conn.execute(
            "SELECT id FROM targets WHERE id=?", (target_id,)).fetchone()
        if row is None:
            return False
        self._active_target_id = int(row["id"])
        # Never persist the reserved (unassigned) bucket as current — a later
        # restore would filter every table to scratch rows. Peeking at it
        # (glyph target show 0) is a one-shot display: leave any previously
        # persisted real target untouched so the current context survives.
        if self._active_target_id != _UNASSIGNED_TARGET_ID:
            self.set_meta(_ACTIVE_TARGET_META, str(self._active_target_id))
        return True

    def clear_active_target(self) -> None:
        """Unset the active target. Reads then return rows across all targets."""
        self._active_target_id = None
        self._clear_active_meta()

    def _restore_active_target(self) -> None:
        """Restore the persisted active target (meta ``active_target_id``),
        if it still exists. Used by display commands that open a fresh
        Catalog so tables show the CURRENT target's rows only. A stale id
        (target removed elsewhere) is cleaned up rather than left behind.
        The reserved unassigned bucket (id=0) is never restored as current
        — it would filter every table to scratch rows (renderers already
        skip it for the "current" marker)."""
        raw = self.get_meta(_ACTIVE_TARGET_META)
        if not raw:
            return
        try:
            tid = int(raw)
        except (ValueError, TypeError):
            self._clear_active_meta()
            return
        if tid == _UNASSIGNED_TARGET_ID:
            self._clear_active_meta()
            return
        row = self.conn.execute(
            "SELECT id FROM targets WHERE id=?", (tid,)).fetchone()
        if row is not None:
            self._active_target_id = tid
        else:
            self._clear_active_meta()

    def _clear_active_meta(self) -> None:
        self.conn.execute(
            "DELETE FROM meta WHERE key=?", (_ACTIVE_TARGET_META,))
        self.conn.commit()

    def targets(self) -> List[Dict[str, Any]]:
        """Every registered target, newest first."""
        rows = self.conn.execute(
            "SELECT t.id AS id, t.host AS host, t.label AS label, "
            "t.notes AS notes, t.created_at AS created_at, "
            "(SELECT COUNT(*) FROM flows WHERE target_id = t.id) AS flows "
            "FROM targets t ORDER BY t.id DESC"
        ).fetchall()
        return [
            {"id": r["id"], "host": r["host"], "label": r["label"],
             "notes": r["notes"], "created_at": r["created_at"],
             "flows": int(r["flows"] or 0)}
            for r in rows
        ]

    def get_target(self, target_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT id, host, label, notes, created_at FROM targets WHERE id=?",
            (target_id,),
        ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "host": row["host"], "label": row["label"],
                "notes": row["notes"], "created_at": row["created_at"]}

    def resolve_target(self, host_or_id: str) -> Optional[int]:
        """Resolve a CLI argument (host or numeric id) to a target id."""
        try:
            tid = int(host_or_id)
        except ValueError:
            row = self.conn.execute(
                "SELECT id FROM targets WHERE host=?",
                (host_or_id.strip().lower(),),
            ).fetchone()
            return int(row["id"]) if row else None
        row = self.conn.execute(
            "SELECT id FROM targets WHERE id=?", (tid,)).fetchone()
        return int(row["id"]) if row else None

    def remove_target(self, target_id: int) -> bool:
        """Delete a target AND every row that belongs to it. The active
        target is cleared if it was the one removed."""
        row = self.conn.execute(
            "SELECT id FROM targets WHERE id=?", (target_id,)).fetchone()
        if row is None:
            return False
        for tbl in _DATA_TABLES:
            self.conn.execute(
                f"DELETE FROM {tbl} WHERE target_id=?", (target_id,))
        self.conn.execute("DELETE FROM targets WHERE id=?", (target_id,))
        if (self._active_target_id == target_id
                or self.get_meta(_ACTIVE_TARGET_META) == str(target_id)):
            self._active_target_id = None
            self._clear_active_meta()
        self.conn.commit()
        return True

    def clear_target(self, target_id: Optional[int] = None) -> int:
        """Drop every data row for the active (or specified) target, but
        KEEP the target row in ``targets``. This is the per-run idempotent
        reset — a re-run of the same target replaces its data without
        touching other targets. Returns the target_id that was cleared, or
        ``None`` if no target was active/specified."""
        tid = target_id if target_id is not None else self._active_target_id
        if tid is None:
            return None
        for tbl in _DATA_TABLES:
            self.conn.execute(
                f"DELETE FROM {tbl} WHERE target_id=?", (tid,))
        self.conn.commit()
        return tid

    # -- write/read target helpers ---------------------------------------
    def _wtid(self, target_id: Optional[int]) -> int:
        """Resolve the target_id to stamp on a write. Explicit > active >
        the reserved unassigned target (id=0). Never returns NULL — every
        data row gets a real target_id so UNIQUE constraints dedup."""
        if target_id is not None:
            return target_id
        if self._active_target_id is not None:
            return self._active_target_id
        return _UNASSIGNED_TARGET_ID

    def _target_filter(self, target_id: Optional[int],
                       all_targets: bool) -> tuple:
        """Build a ``WHERE target_id <op> ?`` clause + param.

        - ``all_targets=True`` → no filter (return all rows).
        - ``target_id`` is an int → filter to that target.
        - ``target_id`` is None → filter to the active target if one is
          set, else no filter (all rows).
        """
        if all_targets:
            return "", ()
        if target_id is not None:
            return "WHERE target_id=?", (target_id,)
        if self._active_target_id is not None:
            return "WHERE target_id=?", (self._active_target_id,)
        return "", ()

    # -- endpoints --------------------------------------------------------
    def upsert_endpoint(self, method: str, host: str, path_template: str,
                        *, target_id: Optional[int] = None) -> int:
        tid = self._wtid(target_id)
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO endpoints (target_id, method, host, "
            "path_template) VALUES (?, ?, ?, ?)",
            (tid, method.upper(), host, path_template),
        )
        if cur.lastrowid and cur.rowcount:
            self.conn.commit()
            return int(cur.lastrowid)
        # INSERT was ignored (UNIQUE conflict). Look up by shape + target.
        # On migrated DBs the UNIQUE may still be the old (method, host,
        # path_template) — fall back to a shape-only match if the
        # target-scoped lookup misses.
        row = self.conn.execute(
            "SELECT id FROM endpoints WHERE target_id IS ? AND method=? "
            "AND host=? AND path_template=?",
            (tid, method.upper(), host, path_template),
        ).fetchone()
        if row is None:
            row = self.conn.execute(
                "SELECT id FROM endpoints WHERE method=? AND host=? "
                "AND path_template=? ORDER BY id LIMIT 1",
                (method.upper(), host, path_template),
            ).fetchone()
        return int(row["id"]) if row else None  # type: ignore[return-value]

    def set_reachability(self, endpoint_id: int, reachability: str,
                         note: Optional[str] = None) -> None:
        self.conn.execute(
            "UPDATE endpoints SET reachability=?, reachability_note=? WHERE id=?",
            (reachability, note, endpoint_id),
        )
        self.conn.commit()

    def endpoints(self, *, target_id: Optional[int] = None,
                  all_targets: bool = False) -> List[Endpoint]:
        where, params = self._target_filter(target_id, all_targets)
        rows = self.conn.execute(
            f"SELECT * FROM endpoints {where} "
            "ORDER BY host, path_template, method", tuple(params)
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
    def add_flow(self, flow: Flow, *, target_id: Optional[int] = None) -> int:
        """Persist a flow, deriving and linking its endpoint."""
        tid = self._wtid(target_id)
        if not flow.host or not flow.path:
            host, path, query = split_url(flow.url)
            flow.host = flow.host or host
            flow.path = flow.path or path
            flow.query = flow.query or query
        endpoint_id = self.upsert_endpoint(
            flow.method, flow.host, template_path(flow.path), target_id=tid
        )
        cur = self.conn.execute(
            "INSERT INTO flows (target_id, endpoint_id, method, url, host, "
            "path, query, req_headers, req_body, status, resp_headers, "
            "resp_body, resp_mime, started_at, source) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tid, endpoint_id, flow.method.upper(), flow.url, flow.host,
                flow.path, _dumps(flow.query), _dumps(flow.req_headers),
                flow.req_body, flow.status, _dumps(flow.resp_headers),
                flow.resp_body, flow.resp_mime, flow.started_at, flow.source,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_flows(self, flows: Iterable[Flow],
                  *, target_id: Optional[int] = None) -> int:
        count = 0
        for flow in flows:
            self.add_flow(flow, target_id=target_id)
            count += 1
        return count

    def flows_for_endpoint(self, endpoint_id: int) -> List[Flow]:
        rows = self.conn.execute(
            "SELECT * FROM flows WHERE endpoint_id=?", (endpoint_id,)
        ).fetchall()
        return [self._row_to_flow(r) for r in rows]

    def all_flows(self, *, target_id: Optional[int] = None,
                  all_targets: bool = False) -> List[Flow]:
        where, params = self._target_filter(target_id, all_targets)
        rows = self.conn.execute(
            f"SELECT * FROM flows {where}", tuple(params)
        ).fetchall()
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
    def upsert_field(self, f: ObservedField,
                     *, target_id: Optional[int] = None) -> int:
        tid = self._wtid(target_id)
        cur = self.conn.execute(
            "INSERT INTO fields (target_id, endpoint_id, location, json_path, "
            "json_type, sample_values, distinct_count, total_count, "
            "is_enum_candidate) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(target_id, endpoint_id, location, json_path) "
            "DO UPDATE SET "
            "json_type=excluded.json_type, sample_values=excluded.sample_values, "
            "distinct_count=excluded.distinct_count, total_count=excluded.total_count, "
            "is_enum_candidate=excluded.is_enum_candidate",
            (
                tid, f.endpoint_id, f.location, f.json_path, f.json_type,
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

    def enum_candidates(self, *, target_id: Optional[int] = None,
                        all_targets: bool = False) -> List[ObservedField]:
        where, params = self._target_filter(target_id, all_targets)
        rows = self.conn.execute(
            f"SELECT * FROM fields {where} AND is_enum_candidate=1 "
            if where else
            "SELECT * FROM fields WHERE is_enum_candidate=1",
            tuple(params),
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
    def upsert_dictionary(self, e: DictionaryEntry,
                          *, target_id: Optional[int] = None) -> int:
        # A re-run of Rosetta must never overwrite a human decision: the
        # WHERE clause skips the update for any row a human has reviewed.
        tid = self._wtid(target_id)
        cur = self.conn.execute(
            "INSERT INTO dictionary (target_id, endpoint_id, json_path, code, "
            "meaning, confidence, strategy, evidence, needs_review) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(target_id, endpoint_id, json_path, code) DO UPDATE SET "
            "meaning=excluded.meaning, confidence=excluded.confidence, "
            "strategy=excluded.strategy, evidence=excluded.evidence, "
            "needs_review=excluded.needs_review "
            "WHERE dictionary.review_state IS NULL "
            "AND excluded.confidence >= dictionary.confidence",
            (
                tid, e.endpoint_id, e.json_path, _dumps(e.code), e.meaning,
                e.confidence, e.strategy, e.evidence, 1 if e.needs_review else 0,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def dictionary(self, needs_review: Optional[bool] = None,
                   review_state: Optional[str] = None,
                   include_rejected: bool = False,
                   *, target_id: Optional[int] = None,
                   all_targets: bool = False) -> List[DictionaryEntry]:
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
        if all_targets:
            where = ""
        elif target_id is not None:
            where = "WHERE target_id=?"
            params.insert(0, target_id)
        elif self._active_target_id is not None:
            where = "WHERE target_id=?"
            params.insert(0, self._active_target_id)
        else:
            where = ""
        if clauses:
            joiner = " AND " if where else "WHERE "
            where += joiner + " AND ".join(clauses)
        sql = f"SELECT * FROM dictionary {where} ORDER BY confidence DESC"
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
    def add_page(self, page: PageObservation,
                 *, target_id: Optional[int] = None) -> int:
        tid = self._wtid(target_id)
        cur = self.conn.execute(
            "INSERT INTO page_observations (target_id, url, html, text, labels, "
            "observed_at) VALUES (?,?,?,?,?,?)",
            (tid, page.url, page.html, page.text, _dumps(page.labels),
             page.observed_at),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def pages(self, *, target_id: Optional[int] = None,
              all_targets: bool = False) -> List[PageObservation]:
        where, params = self._target_filter(target_id, all_targets)
        rows = self.conn.execute(
            f"SELECT * FROM page_observations {where}", tuple(params)
        ).fetchall()
        return [
            PageObservation(
                id=r["id"], url=r["url"], html=r["html"], text=r["text"],
                labels=_loads(r["labels"], []), observed_at=r["observed_at"],
            )
            for r in rows
        ]

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
    def add_finding(self, f: Finding,
                    *, target_id: Optional[int] = None) -> int:
        tid = self._wtid(target_id)
        cur = self.conn.execute(
            "INSERT INTO findings (target_id, kind, category, severity, "
            "location, evidence, endpoint_id, value_sample, party, host, score) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(target_id, kind, category, endpoint_id, location) "
            "DO UPDATE SET "
            "severity=excluded.severity, evidence=excluded.evidence, "
            "value_sample=excluded.value_sample, party=excluded.party, "
            "host=excluded.host, score=excluded.score",
            (tid, f.kind, f.category, f.severity, f.location, f.evidence,
             f.endpoint_id, f.value_sample, f.party, f.host, f.score),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def findings(self, kind: Optional[str] = None,
                 min_severity: Optional[str] = None,
                 party: Optional[str] = None,
                 *, target_id: Optional[int] = None,
                 all_targets: bool = False) -> List[Finding]:
        clauses: List[str] = []
        params: List[Any] = []
        if kind is not None:
            clauses.append("kind=?")
            params.append(kind)
        if party is not None:
            clauses.append("party=?")
            params.append(party)
        if all_targets:
            where = ""
        elif target_id is not None:
            where = "WHERE target_id=?"
            params.insert(0, target_id)
        elif self._active_target_id is not None:
            where = "WHERE target_id=?"
            params.insert(0, self._active_target_id)
        else:
            where = ""
        if clauses:
            joiner = " AND " if where else "WHERE "
            where += joiner + " AND ".join(clauses)
        sql = f"SELECT * FROM findings {where}"
        rows = self.conn.execute(sql, tuple(params)).fetchall()
        out = [
            Finding(
                id=r["id"], kind=r["kind"], category=r["category"],
                severity=r["severity"], location=r["location"],
                evidence=r["evidence"], endpoint_id=r["endpoint_id"],
                value_sample=r["value_sample"], party=r["party"], host=r["host"],
                score=r["score"] if "score" in r.keys() else None,
            )
            for r in rows
        ]
        if min_severity is not None:
            cutoff = severity_rank(min_severity)
            out = [f for f in out if severity_rank(f.severity) <= cutoff]
        out.sort(key=lambda f: (severity_rank(f.severity), f.kind, f.category))
        return out

    def clear_findings(self, kind: Optional[str] = None,
                       *, target_id: Optional[int] = None) -> None:
        """Drop findings so a re-scan is idempotent.

        With ``kind``, only that kind is cleared (e.g. re-running the SNI
        hunt wipes ``sni_bug_host`` rows but leaves ``sensitive`` findings
        intact). Without ``kind``, all findings are cleared (the original
        behavior — used by the sensitive scan, which is the first stage to
        write findings and owns the full reset).

        Scoped to the active (or specified) target by default — set
        ``target_id=None`` AND pass no active target to clear across all
        targets (legacy behavior, used by tests).
        """
        tid = target_id if target_id is not None else self._active_target_id
        if kind is None:
            if tid is not None:
                self.conn.execute(
                    "DELETE FROM findings WHERE target_id=?", (tid,))
            else:
                self.conn.execute("DELETE FROM findings")
        else:
            if tid is not None:
                self.conn.execute(
                    "DELETE FROM findings WHERE kind=? AND target_id=?",
                    (kind, tid))
            else:
                self.conn.execute("DELETE FROM findings WHERE kind=?", (kind,))
        self.conn.commit()

    # -- vpn configs (ADR-11: VPN-Config Decoder) -------------------------
    def add_vpn_config(self, cfg, *, target_id: Optional[int] = None) -> int:
        """Persist a decoded :class:`~glyph.vpndec.models.VpnConfig`.

        Upserts on ``(target_id, filepath)`` — re-decoding the same file
        for the same target replaces the row. Credentials (ssh_user/ssh_pass)
        are KEPT (ADR-4 precedent).
        """
        tid = self._wtid(target_id)
        cur = self.conn.execute(
            "INSERT INTO vpn_configs (target_id, filepath, filename, format, "
            "is_encrypted, decryption_status, scheme, confidence, key_label, "
            "host, port, protocol, ssh_server, ssh_port, ssh_user, ssh_pass, "
            "proxy_host, proxy_port, payload, sni, bug_host, dns, remote_dns, "
            "raw_data, errors, warnings, decoded_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(target_id, filepath) DO UPDATE SET "
            "filename=excluded.filename, format=excluded.format, "
            "is_encrypted=excluded.is_encrypted, "
            "decryption_status=excluded.decryption_status, "
            "scheme=excluded.scheme, confidence=excluded.confidence, "
            "key_label=excluded.key_label, host=excluded.host, port=excluded.port, "
            "protocol=excluded.protocol, ssh_server=excluded.ssh_server, "
            "ssh_port=excluded.ssh_port, ssh_user=excluded.ssh_user, "
            "ssh_pass=excluded.ssh_pass, proxy_host=excluded.proxy_host, "
            "proxy_port=excluded.proxy_port, payload=excluded.payload, "
            "sni=excluded.sni, bug_host=excluded.bug_host, dns=excluded.dns, "
            "remote_dns=excluded.remote_dns, raw_data=excluded.raw_data, "
            "errors=excluded.errors, warnings=excluded.warnings, "
            "decoded_at=excluded.decoded_at",
            (tid, cfg.filepath, cfg.filename, cfg.format,
             1 if cfg.is_encrypted else 0, cfg.decryption_status, cfg.scheme,
             cfg.confidence, cfg.key_label, cfg.host, cfg.port, cfg.protocol,
             cfg.ssh_server, cfg.ssh_port, cfg.ssh_user, cfg.ssh_pass,
             cfg.proxy_host, cfg.proxy_port, cfg.payload, cfg.sni,
             cfg.bug_host, cfg.dns, cfg.remote_dns, _dumps(cfg.raw_data),
             _dumps(cfg.errors), _dumps(cfg.warnings), _now()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def vpn_configs(self, *, target_id: Optional[int] = None,
                    all_targets: bool = False) -> List[Dict[str, Any]]:
        """Return decoded VPN configs, newest first."""
        where, params = self._target_filter(target_id, all_targets)
        rows = self.conn.execute(
            f"SELECT * FROM vpn_configs {where} ORDER BY id DESC", tuple(params)
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"], "target_id": r["target_id"],
                "filepath": r["filepath"], "filename": r["filename"],
                "format": r["format"], "is_encrypted": bool(r["is_encrypted"]),
                "decryption_status": r["decryption_status"], "scheme": r["scheme"],
                "confidence": r["confidence"], "key_label": r["key_label"],
                "host": r["host"], "port": r["port"], "protocol": r["protocol"],
                "ssh_server": r["ssh_server"], "ssh_port": r["ssh_port"],
                "ssh_user": r["ssh_user"], "ssh_pass": r["ssh_pass"],
                "proxy_host": r["proxy_host"], "proxy_port": r["proxy_port"],
                "payload": r["payload"], "sni": r["sni"], "bug_host": r["bug_host"],
                "dns": r["dns"], "remote_dns": r["remote_dns"],
                "raw_data": _loads(r["raw_data"], None),
                "errors": _loads(r["errors"], []) or [],
                "warnings": _loads(r["warnings"], []) or [],
                "decoded_at": r["decoded_at"],
            })
        return out

    def clear_vpn_configs(self, *, target_id: Optional[int] = None) -> None:
        """Drop decoded VPN configs (for the active/specified target, or all)."""
        tid = target_id if target_id is not None else self._active_target_id
        if tid is not None:
            self.conn.execute(
                "DELETE FROM vpn_configs WHERE target_id=?", (tid,))
        else:
            self.conn.execute("DELETE FROM vpn_configs")
        self.conn.commit()

    def reset(self) -> None:
        """Empty the ENTIRE catalog — every target, every row. A fresh
        start. Keeps the schema; clears all captured data, analysis, and
        meta (except version). Use :meth:`clear_target` for the per-target
        idempotent reset; this is for tests + an explicit ``--reset`` flag."""
        for tbl in _DATA_TABLES:
            self.conn.execute("DELETE FROM " + tbl)
        self.conn.execute("DELETE FROM targets")
        self.conn.execute("DELETE FROM meta WHERE key != 'schema_version'")
        self._active_target_id = None
        self.conn.commit()

    # -- convenience ------------------------------------------------------
    def summary(self, *, target_id: Optional[int] = None,
                all_targets: bool = False) -> Dict[str, int]:
        """Headline counts. Defaults to the active target if one is set,
        else all targets (pass ``all_targets=True`` to force all, or an
        explicit ``target_id`` for a specific one)."""
        tid = target_id if target_id is not None else (
            None if all_targets else self._active_target_id)

        def count(table: str) -> int:
            if tid is None:
                return int(self.conn.execute(
                    f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            return int(self.conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE target_id=?",
                (tid,)).fetchone()["n"])

        enum_count = 0
        if tid is None:
            enum_count = int(self.conn.execute(
                "SELECT COUNT(*) AS n FROM fields WHERE is_enum_candidate=1"
            ).fetchone()["n"])
        else:
            enum_count = int(self.conn.execute(
                "SELECT COUNT(*) AS n FROM fields WHERE is_enum_candidate=1 "
                "AND target_id=?", (tid,)).fetchone()["n"])

        out = {
            "endpoints": count("endpoints"),
            "flows": count("flows"),
            "fields": count("fields"),
            "findings": count("findings"),
            "enum_candidates": enum_count,
            "dictionary": count("dictionary"),
            "pages": count("page_observations"),
            "vpn_configs": count("vpn_configs"),
        }
        out["targets"] = int(self.conn.execute(
            "SELECT COUNT(*) AS n FROM targets").fetchone()["n"])
        return out


# v4 rebuild DDL — the new shape of each data table (with target_id and the
# new UNIQUEs). Used only by _migrate_to_v4 to rebuild pre-v4 catalogs; fresh
# DBs get these from _SCHEMA directly. Kept in sync with _SCHEMA by hand.
_V4_REBUILDS: Dict[str, str] = {
    "flows": """CREATE TABLE flows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER,
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
    )""",
    "endpoints": """CREATE TABLE endpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER,
        method TEXT NOT NULL,
        host TEXT NOT NULL,
        path_template TEXT NOT NULL,
        reachability TEXT DEFAULT 'direct',
        reachability_note TEXT,
        UNIQUE (target_id, method, host, path_template)
    )""",
    "fields": """CREATE TABLE fields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER,
        endpoint_id INTEGER NOT NULL,
        location TEXT NOT NULL,
        json_path TEXT NOT NULL,
        json_type TEXT,
        sample_values TEXT,
        distinct_count INTEGER,
        total_count INTEGER,
        is_enum_candidate INTEGER DEFAULT 0,
        UNIQUE (target_id, endpoint_id, location, json_path)
    )""",
    "dictionary": """CREATE TABLE dictionary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER,
        endpoint_id INTEGER,
        json_path TEXT NOT NULL,
        code TEXT NOT NULL,
        meaning TEXT,
        confidence REAL,
        strategy TEXT,
        evidence TEXT,
        needs_review INTEGER DEFAULT 0,
        review_state TEXT,
        UNIQUE (target_id, endpoint_id, json_path, code)
    )""",
    "page_observations": """CREATE TABLE page_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER,
        url TEXT NOT NULL,
        html TEXT,
        text TEXT,
        labels TEXT,
        observed_at TEXT
    )""",
    "findings": """CREATE TABLE findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER,
        kind TEXT NOT NULL,
        category TEXT NOT NULL,
        severity TEXT NOT NULL,
        location TEXT NOT NULL,
        evidence TEXT,
        endpoint_id INTEGER,
        value_sample TEXT,
        party TEXT,
        host TEXT,
        score INTEGER,
        UNIQUE (target_id, kind, category, endpoint_id, location)
    )""",
    "vpn_configs": """CREATE TABLE vpn_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER,
        filepath TEXT NOT NULL,
        filename TEXT NOT NULL,
        format TEXT NOT NULL,
        is_encrypted INTEGER DEFAULT 0,
        decryption_status TEXT NOT NULL,
        scheme TEXT,
        confidence REAL DEFAULT 0.0,
        key_label TEXT,
        host TEXT,
        port INTEGER,
        protocol TEXT,
        ssh_server TEXT,
        ssh_port INTEGER,
        ssh_user TEXT,
        ssh_pass TEXT,
        proxy_host TEXT,
        proxy_port INTEGER,
        payload TEXT,
        sni TEXT,
        bug_host TEXT,
        dns TEXT,
        remote_dns TEXT,
        raw_data TEXT,
        errors TEXT,
        warnings TEXT,
        decoded_at TEXT,
        UNIQUE (target_id, filepath)
    )""",
}
