"""Application orchestration: validate, persist, execute and retain evidence."""
from __future__ import annotations

from typing import Callable

from .comparison import RunComparisonService
from .errors import Conflict, WorkspaceError
from .models import ExecutionRecord, ScenarioRevision, input_object, project_identifier
from .repository import SQLiteWorkspaceRepository


class WorkspaceService:
    def __init__(self, repository: SQLiteWorkspaceRepository, executor: Callable,
                 installed_projects: Callable, mode: str = "local"):
        if mode not in {"local", "live"}:
            raise WorkspaceError("Unsupported execution mode.")
        self.repository = repository
        self.executor = executor
        self.installed_projects = installed_projects
        self.mode = mode
        self.comparison = RunComparisonService()

    def _project(self, project_id: str):
        project_identifier(project_id)
        project = self.installed_projects().get(project_id)
        if project is None:
            raise WorkspaceError("Application is not installed in this workspace.")
        return project

    def save_scenario(self, project_id: str, name: str, payload: dict, scenario_id=None, expected_version=None) -> ScenarioRevision:
        self._project(project_id)
        return self.repository.save_scenario(project_id, name, payload, scenario_id, expected_version)

    def execute(self, project_id: str, payload: dict | None = None, *, scenario_id=None,
                scenario_version=None, idempotency_key=None) -> ExecutionRecord:
        project = self._project(project_id)
        if scenario_id is not None:
            if scenario_version is None:
                raise WorkspaceError("Select an explicit scenario revision before execution.")
            scenario = self.repository.get_scenario(scenario_id, scenario_version)
            if scenario.project_id != project_id or scenario.archived:
                raise Conflict("Scenario is archived or belongs to another application.")
            if payload is not None and input_object(payload) != scenario.payload:
                raise Conflict("Payload differs from the selected scenario revision.")
            payload = scenario.payload
        elif scenario_version is not None:
            raise WorkspaceError("Scenario identity is required with a revision.")
        payload = input_object(project.default_input() if payload is None else payload)
        record, created = self.repository.reserve_execution(
            project_id, payload, self.mode, scenario_id=scenario_id,
            scenario_version=scenario_version, idempotency_key=idempotency_key,
        )
        if not created:
            return record
        try:
            report = self.executor(project_id, payload, self.mode)
            return self.repository.finish_execution(record.run_id, report=report)
        except (ValueError, TypeError, KeyError, OSError) as error:
            # Provider adapters sanitize external envelopes before this boundary.
            return self.repository.finish_execution(record.run_id, error=str(error)[:500] or "Execution failed validation.")
        except Exception:
            self.repository.finish_execution(record.run_id, error="Unexpected application failure; inspect local service logs before retrying.")
            raise

    def compare(self, left_run_id: str, right_run_id: str) -> dict:
        return self.comparison.compare(self.repository.get_execution(left_run_id), self.repository.get_execution(right_run_id))
