"""Transactional SQLite adapter for workspace state, execution evidence and reviews."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from .errors import Conflict, NotFound, WorkspaceError
from .migrations import migrate, SCHEMA_VERSION
from .models import (
    ExecutionRecord, ScenarioRevision, REVIEW_TRANSITIONS, canonical, digest,
    identifier, input_object, label, project_identifier, revision_number, timestamp,
)


class SQLiteWorkspaceRepository:
    """One connection per transaction; optimistic revisions prevent lost updates.

    Calculation and provider calls occur outside database transactions. The audit
    chain detects accidental or out-of-band changes when compared to a trusted
    checkpoint; a database administrator can rewrite it and is not distrusted.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            migrate(connection)
        self.path.chmod(0o600)

    @contextmanager
    def _connection(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except BaseException:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _audit(connection, kind: str, entity_id: str, details: dict) -> None:
        previous = connection.execute("SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1").fetchone()
        previous_hash = previous[0] if previous else "0" * 64
        event = {"event_id": identifier(), "occurred_at": timestamp(), "kind": kind,
                 "entity_id": entity_id, "details": details, "previous_hash": previous_hash}
        event_hash = digest(event)
        connection.execute(
            "INSERT INTO audit_events(event_id,occurred_at,kind,entity_id,details,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?)",
            (event["event_id"], event["occurred_at"], kind, entity_id, canonical(details), previous_hash, event_hash),
        )

    def save_scenario(self, project_id: str, name: str, payload: dict,
                      scenario_id: str | None = None, expected_version: int | None = None) -> ScenarioRevision:
        project_id, name, payload = project_identifier(project_id), label(name, "Scenario name"), input_object(payload)
        now = timestamp()
        with self._connection(write=True) as connection:
            if scenario_id is None:
                if expected_version is not None:
                    raise WorkspaceError("A new scenario cannot have an expected revision.")
                scenario_id, version = identifier(), 1
                connection.execute("INSERT INTO scenarios VALUES(?,?,?,?,?,?)", (scenario_id, project_id, name, version, 0, now))
            else:
                scenario_id = label(scenario_id, "Scenario identity", 160)
                expected_version = revision_number(expected_version)
                row = connection.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
                if row is None:
                    raise NotFound("Scenario not found.")
                if row["project_id"] != project_id:
                    raise Conflict("A scenario cannot move to another application.")
                if row["current_version"] != expected_version or row["archived"]:
                    raise Conflict("Scenario was changed or archived. Reload its current revision.")
                version = expected_version + 1
                connection.execute("UPDATE scenarios SET name=?,current_version=? WHERE id=?", (name, version, scenario_id))
            connection.execute("INSERT INTO scenario_revisions VALUES(?,?,?,?,?)", (scenario_id, version, name, canonical(payload), now))
            self._audit(connection, "scenario.created" if version == 1 else "scenario.revised", scenario_id,
                        {"version": version, "project_id": project_id, "input_sha256": digest(payload)})
        return ScenarioRevision(scenario_id, project_id, name, version, payload, now)

    def get_scenario(self, scenario_id: str, version: int | None = None) -> ScenarioRevision:
        scenario_id = label(scenario_id, "Scenario identity", 160)
        if version is not None:
            revision_number(version)
        with self._connection() as connection:
            scenario = connection.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
            if scenario is None:
                raise NotFound("Scenario not found.")
            revision = connection.execute("SELECT * FROM scenario_revisions WHERE scenario_id=? AND version=?",
                                          (scenario_id, version or scenario["current_version"])).fetchone()
            if revision is None:
                raise NotFound("Scenario revision not found.")
            return ScenarioRevision(scenario_id, scenario["project_id"], revision["name"], revision["version"],
                                    json.loads(revision["payload"]), revision["created_at"], bool(scenario["archived"]))

    def list_scenarios(self, project_id: str, include_archived: bool = False, limit: int = 100) -> list[dict]:
        self._limit(limit)
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id,project_id,name,current_version AS version,archived,created_at FROM scenarios "
                "WHERE project_id=? AND (? OR archived=0) ORDER BY created_at DESC,id LIMIT ?",
                (project_id, int(include_archived), limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def archive_scenario(self, scenario_id: str, expected_version: int, archived: bool = True) -> ScenarioRevision:
        scenario_id = label(scenario_id, "Scenario identity", 160)
        revision_number(expected_version)
        if type(archived) is not bool:
            raise WorkspaceError("Archived must be a boolean.")
        with self._connection(write=True) as connection:
            row = connection.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
            if row is None:
                raise NotFound("Scenario not found.")
            if row["current_version"] != expected_version:
                raise Conflict("Scenario revision changed. Reload before archiving.")
            if bool(row["archived"]) != archived:
                connection.execute("UPDATE scenarios SET archived=? WHERE id=?", (int(archived), scenario_id))
                self._audit(connection, "scenario.archived" if archived else "scenario.restored", scenario_id, {"version": expected_version})
        return self.get_scenario(scenario_id)

    def reserve_execution(self, project_id: str, payload: dict, mode: str = "local", *, scenario_id: str | None = None,
                          scenario_version: int | None = None, idempotency_key: str | None = None) -> tuple[ExecutionRecord, bool]:
        project_id, payload = project_identifier(project_id), input_object(payload)
        if mode not in {"local", "live"}:
            raise WorkspaceError("Execution mode must be local or live.")
        if idempotency_key is not None:
            idempotency_key = label(idempotency_key, "Idempotency key", 160)
        if (scenario_id is None) != (scenario_version is None):
            raise WorkspaceError("Scenario identity and revision must be supplied together.")
        if scenario_id is not None:
            scenario_id = label(scenario_id, "Scenario identity", 160)
        request_hash = digest({"project_id": project_id, "payload": payload, "mode": mode,
                               "scenario_id": scenario_id, "scenario_version": scenario_version})
        with self._connection(write=True) as connection:
            if scenario_id is not None:
                revision_number(scenario_version)
                row = connection.execute(
                    "SELECT s.project_id,s.archived,r.payload FROM scenario_revisions r JOIN scenarios s ON s.id=r.scenario_id "
                    "WHERE r.scenario_id=? AND r.version=?", (scenario_id, scenario_version),
                ).fetchone()
                if row is None or row["archived"] or row["project_id"] != project_id or row["payload"] != canonical(payload):
                    raise Conflict("Execution does not match the referenced scenario revision.")
            if idempotency_key:
                row = connection.execute("SELECT * FROM executions WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if row:
                    if row["request_hash"] != request_hash:
                        raise Conflict("Idempotency key already belongs to a different execution request.")
                    return self._execution(row), False
            run_id, now = identifier(), timestamp()
            connection.execute(
                "INSERT INTO executions(id,project_id,status,payload,started_at,scenario_id,scenario_version,mode,idempotency_key,request_hash) "
                "VALUES(?,?,'running',?,?,?,?,?,?,?)",
                (run_id, project_id, canonical(payload), now, scenario_id, scenario_version, mode, idempotency_key, request_hash),
            )
            self._audit(connection, "execution.started", run_id, {"project_id": project_id, "input_sha256": digest(payload), "mode": mode})
            row = connection.execute("SELECT * FROM executions WHERE id=?", (run_id,)).fetchone()
            return self._execution(row), True

    def finish_execution(self, run_id: str, report: dict | None = None, error: str | None = None) -> ExecutionRecord:
        run_id = label(run_id, "Execution identity", 160)
        if (report is None) == (error is None):
            raise WorkspaceError("Finish with either a report or an error.")
        if report is not None and not isinstance(report, dict):
            raise WorkspaceError("Execution report must be an object.")
        report_json = canonical(report) if report is not None else None
        error = label(error, "Failure description", 500) if error is not None else None
        with self._connection(write=True) as connection:
            row = connection.execute("SELECT status FROM executions WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise NotFound("Execution not found.")
            if row["status"] != "running":
                raise Conflict("Execution has already reached a terminal state.")
            status = "failed" if error else "succeeded"
            connection.execute("UPDATE executions SET status=?,finished_at=?,report=?,error=? WHERE id=?",
                               (status, timestamp(), report_json, error, run_id))
            self._audit(connection, "execution." + status, run_id, {"report_sha256": digest(report) if report else None})
        return self.get_execution(run_id)

    @staticmethod
    def _execution(row) -> ExecutionRecord:
        return ExecutionRecord(row["id"], row["project_id"], row["status"], json.loads(row["payload"]),
                               row["started_at"], row["finished_at"], json.loads(row["report"]) if row["report"] else None,
                               row["error"], row["scenario_id"], row["scenario_version"], row["mode"],
                               row["review_status"], row["review_version"])

    def get_execution(self, run_id: str) -> ExecutionRecord:
        run_id = label(run_id, "Execution identity", 160)
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM executions WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise NotFound("Execution not found.")
            return self._execution(row)

    def list_executions(self, project_id: str, limit: int = 100) -> list[dict]:
        self._limit(limit)
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM executions WHERE project_id=? ORDER BY started_at DESC,id LIMIT ?",
                                      (project_id, limit)).fetchall()
            return [self._execution(row).to_dict(include_evidence=False) for row in rows]

    def review_execution(self, run_id: str, decision: str, reviewer: str, note: str, expected_version: int) -> ExecutionRecord:
        run_id = label(run_id, "Execution identity", 160)
        decision = label(decision, "Review decision", 40)
        reviewer, note = label(reviewer, "Reviewer", 100), label(note, "Review rationale", 2000)
        if type(expected_version) is not int or expected_version < 0:
            raise WorkspaceError("Review revision must be a nonnegative integer.")
        with self._connection(write=True) as connection:
            row = connection.execute("SELECT * FROM executions WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise NotFound("Execution not found.")
            if row["status"] != "succeeded":
                raise Conflict("Only a completed successful execution can be reviewed.")
            if row["review_version"] != expected_version:
                raise Conflict("Review was changed by another operation. Reload before deciding.")
            if decision not in REVIEW_TRANSITIONS.get(row["review_status"], set()):
                raise Conflict("That review transition is not permitted.")
            connection.execute("UPDATE executions SET review_status=?,review_version=review_version+1 WHERE id=?", (decision, run_id))
            self._audit(connection, "execution.reviewed", run_id,
                        {"from": row["review_status"], "to": decision, "reviewer": reviewer, "note": note,
                         "review_version": expected_version + 1, "report_sha256": digest(json.loads(row["report"]))})
        return self.get_execution(run_id)

    def recover_interrupted(self) -> int:
        """Exclusive maintenance operation, never while executions are active."""
        with self._connection(write=True) as connection:
            rows = connection.execute("SELECT id FROM executions WHERE status='running'").fetchall()
            for row in rows:
                connection.execute("UPDATE executions SET status='interrupted',finished_at=?,error=? WHERE id=?",
                                   (timestamp(), "Application stopped before completion; create a new run to retry.", row["id"]))
                self._audit(connection, "execution.interrupted", row["id"], {})
            return len(rows)

    @staticmethod
    def _limit(limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise WorkspaceError("List limit must be an integer from 1 to 200.")

    def audit_events(self, limit: int = 100) -> list[dict]:
        self._limit(limit)
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM audit_events ORDER BY sequence DESC LIMIT ?", (limit,)).fetchall()
            return [{**dict(row), "details": json.loads(row["details"])} for row in rows]

    def verify_audit(self) -> dict:
        previous_hash, count = "0" * 64, 0
        with self._connection() as connection:
            for row in connection.execute("SELECT * FROM audit_events ORDER BY sequence"):
                event = {key: row[key] for key in ("event_id", "occurred_at", "kind", "entity_id", "previous_hash")}
                event["details"] = json.loads(row["details"])
                if event["previous_hash"] != previous_hash or digest(event) != row["event_hash"]:
                    return {"valid": False, "events_checked": count, "first_invalid_sequence": row["sequence"]}
                previous_hash, count = row["event_hash"], count + 1
        return {"valid": True, "events_checked": count, "head_hash": previous_hash}

    def diagnostics(self) -> dict:
        with self._connection() as connection:
            return {"schema_version": SCHEMA_VERSION, "storage": "sqlite", "scenarios": connection.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0],
                    "executions": connection.execute("SELECT COUNT(*) FROM executions").fetchone()[0],
                    "audit_events": connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]}
