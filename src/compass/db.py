"""SQLite database layer.

Schema is defined once in ``SCHEMA_SQL`` and applied via ``init_db()``. Tables
mirror the entities laid out in the product spec: CLIN, Workstream,
ProjectSystem, Sprint, SprintKPI, CLINSummary, CustomerValueInput, FeatureValue,
Settings, RiskIssue, AuditLog, User.

We use raw sqlite3 + dict-row factory rather than an ORM to keep the dependency
surface small and the data shapes obvious. The pure-function KPI engine and the
acceptance state machine don't touch the DB at all — they're pluggable into any
storage backend the same way (just pass them dicts).
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def db_path() -> Path:
    return Path(os.getenv("COMPASS_DB_PATH", "compass.db")).resolve()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS clin (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE,             -- e.g. "CLIN 001"
    name         TEXT NOT NULL,
    scope        TEXT,
    status_rag   TEXT,                              -- "green" | "amber" | "red"
    acceptance_decision  TEXT,                      -- "accept" | "conditional" | "reject" | "pending"
    invoice_position     TEXT,                      -- "release" | "hold" | "partial"
    required_cor_action  TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workstream (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    description  TEXT,
    status       TEXT,
    owner_role   TEXT,                              -- "COR" | "PM" | "PO"
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_system (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    workstream_id INTEGER REFERENCES workstream(id),
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS sprint (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_number      INTEGER NOT NULL,
    start_date         TEXT NOT NULL,
    end_date           TEXT NOT NULL,
    clin_id            INTEGER REFERENCES clin(id),
    workstream_id      INTEGER REFERENCES workstream(id),
    project_system_id  INTEGER REFERENCES project_system(id),
    committed_points       REAL NOT NULL,
    completed_points       REAL NOT NULL,
    accepted_stories       INTEGER NOT NULL,
    post_release_defects   INTEGER NOT NULL DEFAULT 0,
    uat_tests              INTEGER NOT NULL DEFAULT 0,
    uat_first_pass_count   INTEGER NOT NULL DEFAULT 0,
    avg_cycle_time_days    REAL NOT NULL DEFAULT 0,
    planned_burn_usd       REAL NOT NULL DEFAULT 0,
    actual_burn_usd        REAL NOT NULL DEFAULT 0,
    availability_pct       REAL NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS customer_value_input (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_id              INTEGER REFERENCES sprint(id),
    clin_id                INTEGER REFERENCES clin(id),
    business_value_rate    REAL NOT NULL DEFAULT 0,   -- 0..1
    user_satisfaction      REAL NOT NULL DEFAULT 0,   -- 0..1
    adoption_rate          REAL NOT NULL DEFAULT 0,   -- 0..1
    rework_rate            REAL NOT NULL DEFAULT 0,   -- 0..1 (inverted in score)
    feature_utilization    REAL NOT NULL DEFAULT 0,   -- 0..1
    created_at             TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS feature_value (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_id                   INTEGER REFERENCES sprint(id),
    clin_id                     INTEGER REFERENCES clin(id),
    workstream_id               INTEGER REFERENCES workstream(id),
    project_system_id           INTEGER REFERENCES project_system(id),
    feature_code                TEXT NOT NULL,                 -- "Feature-001"
    feature_name                TEXT NOT NULL,
    outcome_statement           TEXT,
    target_users                TEXT,
    release_date                TEXT,
    customer_satisfaction       REAL DEFAULT 0,                -- 0..1
    users_surveyed_count        INTEGER DEFAULT 0,
    adoption_rate               REAL DEFAULT 0,                -- 0..1
    feature_utilization         REAL DEFAULT 0,                -- 0..1
    rework_rate                 REAL DEFAULT 0,                -- 0..1
    tangible_evidence           TEXT,                          -- URL or attachment ref
    technical_acceptance_status TEXT,                          -- "accepted" | "rejected" | "pending"
    technical_acceptance_date   TEXT,
    value_validation_start      TEXT,
    value_validation_end        TEXT,
    value_confirmed_yn          INTEGER NOT NULL DEFAULT 0,
    acceptance_stage            TEXT,                          -- "technically_accepted" | "value_pending" | "fully_accepted" | "rework_required"
    payment_status              TEXT,                          -- "released" | "held_pending"
    rework_required_yn          INTEGER NOT NULL DEFAULT 0,
    backlog_impact              TEXT,                          -- "continue" | "reprioritize" | "stop"
    holdback_pct                REAL NOT NULL DEFAULT 0.30,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kpi_name        TEXT NOT NULL UNIQUE,         -- "predictability" | "story_completion" | ...
    green_threshold REAL NOT NULL,
    yellow_threshold REAL NOT NULL,
    direction       TEXT NOT NULL,                -- "high_is_good" | "low_is_good"
    unit            TEXT,                         -- "pct" | "days" | "usd"
    pws_target_text TEXT,
    applies_to      TEXT,                         -- "sprint" | "clin" | "feature"
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS risk_issue (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    priority          TEXT NOT NULL,              -- "high" | "medium" | "low"
    risk_issue_text   TEXT NOT NULL,
    impacted_clin_id  INTEGER REFERENCES clin(id),
    impacted_workstream_id INTEGER REFERENCES workstream(id),
    status            TEXT NOT NULL,              -- "open" | "monitor" | "closed"
    mitigation        TEXT,
    owner_role        TEXT,                       -- "COR" | "PM" | "PO"
    due_date          TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    actor_email TEXT NOT NULL,
    actor_role  TEXT NOT NULL,
    entity      TEXT NOT NULL,
    entity_id   INTEGER,
    action      TEXT NOT NULL,             -- "create" | "update" | "delete" | "decision"
    field       TEXT,
    old_value   TEXT,
    new_value   TEXT,
    rationale   TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL,            -- "COR" | "PM" | "PO" | "READONLY"
    password_hash TEXT NOT NULL,            -- bcrypt
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield a sqlite3 connection with row-as-dict factory and FK enforcement."""
    conn = sqlite3.connect(str(db_path()), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if absent. Idempotent."""
    with _LOCK, connect() as c:
        c.executescript(SCHEMA_SQL)


def is_empty() -> bool:
    """True iff the users table has zero rows — used to gate first-run seeding."""
    row = fetch_one("SELECT COUNT(*) AS n FROM users")
    return (row or {"n": 0}).get("n", 0) == 0


def bootstrap_seed_if_empty() -> bool:
    """First-run only: populate demo CLINs / sprints / features / users.

    Returns True if seeding ran (DB was empty), False otherwise. Safe to call
    on every startup; the empty check makes it a no-op after the first run.
    """
    if not is_empty():
        return False
    # Lazy import to avoid a cycle with auth -> db at module load time.
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from seed_db import (
        seed_clins_workstreams_systems,
        seed_customer_value,
        seed_features,
        seed_risks,
        seed_settings,
        seed_sprints,
        seed_users,
    )

    seed_settings()
    seed_users()
    clin_ids = seed_clins_workstreams_systems()
    seed_sprints(clin_ids)
    seed_customer_value(clin_ids)
    seed_features(clin_ids)
    seed_risks(clin_ids)
    return True


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def fetch_all(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    with connect() as c:
        cur = c.execute(query, params)
        return rows_to_dicts(cur.fetchall())


def fetch_one(query: str, params: tuple = ()) -> dict[str, Any] | None:
    with connect() as c:
        cur = c.execute(query, params)
        r = cur.fetchone()
        return dict(r) if r else None


def execute(query: str, params: tuple = ()) -> int:
    """Execute a write; returns lastrowid (0 if not applicable)."""
    with _LOCK, connect() as c:
        cur = c.execute(query, params)
        return cur.lastrowid or 0
