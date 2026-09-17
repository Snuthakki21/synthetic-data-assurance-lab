"""Versioned SQLite schema; immutable revisions and append-only audit events."""
import sqlite3

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    current_version INTEGER NOT NULL CHECK (current_version > 0),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scenario_revisions (
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    version INTEGER NOT NULL CHECK (version > 0),
    name TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (scenario_id, version)
);
CREATE TABLE IF NOT EXISTS executions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'interrupted')),
    payload TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    report TEXT,
    error TEXT,
    scenario_id TEXT,
    scenario_version INTEGER,
    mode TEXT NOT NULL CHECK (mode IN ('local', 'live')),
    idempotency_key TEXT UNIQUE,
    request_hash TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'unreviewed',
    review_version INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (scenario_id, scenario_version) REFERENCES scenario_revisions(scenario_id, version)
);
CREATE INDEX IF NOT EXISTS execution_project_time ON executions(project_id, started_at DESC);
CREATE TABLE IF NOT EXISTS audit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    occurred_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);
"""


def migrate(connection: sqlite3.Connection) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise ValueError("Workspace was created by a newer application; refusing a schema downgrade.")
    if version == 0:
        connection.executescript("BEGIN IMMEDIATE;" + SCHEMA + "PRAGMA user_version=1; COMMIT;")
