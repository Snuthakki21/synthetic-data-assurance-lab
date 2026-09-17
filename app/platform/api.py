"""Transport-independent REST resource router with explicit command contracts."""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from .errors import Conflict, NotFound, WorkspaceError
from .service import WorkspaceService


class WorkspaceAPI:
    def __init__(self, service: WorkspaceService):
        self.service = service
        self.repository = service.repository

    @staticmethod
    def _body(body: dict | None, allowed: set[str], required: set[str] = frozenset()) -> dict:
        if not isinstance(body, dict) or set(body) - allowed or required - set(body):
            raise WorkspaceError("Request fields do not match this endpoint's command contract.")
        return body

    def dispatch(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        try:
            parsed = urlsplit(path)
            parts = parsed.path.strip("/").split("/")
            if parts[:2] != ["api", "v1"]:
                return 404, {"error": "Unknown API endpoint."}
            resource = parts[2:]
            query = parse_qs(parsed.query)
            if any(len(values) != 1 for values in query.values()):
                raise WorkspaceError("Repeated query parameters are not supported.")
            values = {key: value[0] for key, value in query.items()}
            if method == "GET":
                return self._get(resource, values)
            if method == "POST":
                return self._post(resource, body)
            return 405, {"error": "Method not supported."}
        except NotFound as error:
            return 404, {"error": str(error)}
        except Conflict as error:
            return 409, {"error": str(error)}
        except (WorkspaceError, ValueError, TypeError) as error:
            return 400, {"error": str(error)[:300]}

    def _get(self, resource: list[str], query: dict) -> tuple[int, dict]:
        limit = int(query.get("limit", "100"))
        if resource == ["scenarios"]:
            self.service._project(query.get("project_id"))
            if query.get("archived", "false") not in {"true", "false"}:
                raise WorkspaceError("Archived filter must be true or false.")
            return 200, {"items": self.repository.list_scenarios(query["project_id"], query.get("archived") == "true", limit)}
        if len(resource) == 2 and resource[0] == "scenarios":
            version = int(query["version"]) if "version" in query else None
            return 200, self.repository.get_scenario(resource[1], version).to_dict()
        if resource == ["executions"]:
            self.service._project(query.get("project_id"))
            return 200, {"items": self.repository.list_executions(query["project_id"], limit)}
        if len(resource) == 2 and resource[0] == "executions":
            return 200, self.repository.get_execution(resource[1]).to_dict()
        if resource == ["compare"]:
            return 200, self.service.compare(query.get("left", ""), query.get("right", ""))
        if resource == ["audit"]:
            return 200, {"items": self.repository.audit_events(limit)}
        if resource == ["audit", "integrity"]:
            return 200, self.repository.verify_audit()
        if resource == ["diagnostics"]:
            return 200, {**self.repository.diagnostics(), "mode": self.service.mode,
                         "identity_boundary": "single local operator; reviewer labels are not authentication"}
        return 404, {"error": "Unknown API resource."}

    def _post(self, resource: list[str], body: dict | None) -> tuple[int, dict]:
        if resource == ["scenarios"]:
            data = self._body(body, {"project_id", "name", "payload", "scenario_id", "expected_version"}, {"project_id", "name", "payload"})
            result = self.service.save_scenario(**data)
            return 201, result.to_dict()
        if len(resource) == 3 and resource[0] == "scenarios" and resource[2] == "archive":
            data = self._body(body, {"expected_version", "archived"}, {"expected_version"})
            return 200, self.repository.archive_scenario(resource[1], **data).to_dict()
        if resource == ["executions"]:
            data = self._body(body, {"project_id", "payload", "scenario_id", "scenario_version", "idempotency_key"}, {"project_id"})
            result = self.service.execute(**data)
            return 201, result.to_dict()
        if len(resource) == 3 and resource[0] == "executions" and resource[2] == "review":
            data = self._body(body, {"decision", "reviewer", "note", "expected_version"}, {"decision", "reviewer", "note", "expected_version"})
            if not isinstance(data["decision"], str):
                raise WorkspaceError("Decision must be text.")
            return 200, self.repository.review_execution(resource[1], **data).to_dict()
        return 404, {"error": "Unknown API resource."}
