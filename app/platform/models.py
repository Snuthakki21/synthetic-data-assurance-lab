"""Immutable workspace entities and validation at the storage boundary."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any
from uuid import uuid4

from .errors import WorkspaceError

MAX_INPUT_BYTES = 262_144
MAX_REPORT_BYTES = 16 * 1024 * 1024
REVIEW_TRANSITIONS = {
    "unreviewed": {"approved", "needs_changes", "rejected"},
    "needs_changes": {"approved", "rejected"},
    "approved": {"needs_changes"},
    "rejected": {"needs_changes"},
}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier() -> str:
    return str(uuid4())


def canonical(value: Any, maximum: int = MAX_REPORT_BYTES) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError) as error:
        raise WorkspaceError("Value must be finite, serializable JSON.") from error
    if len(encoded.encode()) > maximum:
        raise WorkspaceError(f"JSON exceeds the {maximum}-byte storage boundary.")
    return encoded


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def input_object(value: Any) -> dict:
    if not isinstance(value, dict):
        raise WorkspaceError("Scenario input must be a JSON object.")
    return json.loads(canonical(value, MAX_INPUT_BYTES))


def label(value: Any, field: str, maximum: int = 120) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise WorkspaceError(f"{field} must contain 1–{maximum} characters.")
    return value.strip()


def project_identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", value):
        raise WorkspaceError("Invalid application identifier.")
    return value


def revision_number(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise WorkspaceError("Expected revision must be a positive integer.")
    return value


@dataclass(frozen=True)
class ScenarioRevision:
    scenario_id: str
    project_id: str
    name: str
    version: int
    payload: dict
    created_at: str
    archived: bool = False

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id, "project_id": self.project_id,
            "name": self.name, "version": self.version, "payload": self.payload,
            "created_at": self.created_at, "archived": self.archived,
            "input_sha256": digest(self.payload),
        }


@dataclass(frozen=True)
class ExecutionRecord:
    run_id: str
    project_id: str
    status: str
    payload: dict
    started_at: str
    finished_at: str | None
    report: dict | None
    error: str | None
    scenario_id: str | None
    scenario_version: int | None
    mode: str
    review_status: str
    review_version: int

    def to_dict(self, include_evidence: bool = True) -> dict:
        result = dict(vars(self))
        if not include_evidence:
            result.pop("payload")
            result.pop("report")
        result["input_sha256"] = digest(self.payload)
        if self.report:
            result["summary"] = self.report.get("summary", "")
        return result
