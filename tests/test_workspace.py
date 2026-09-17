"""Workspace contracts: persistence, concurrency, provenance, HTTP and recovery."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
from functools import partial
import hashlib
import http.client
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.platform.api import WorkspaceAPI
from app.platform.cli import workspace_command
from app.platform.comparison import RunComparisonService
from app.platform.config import WorkspaceSettings
from app.platform.errors import Conflict, NotFound, WorkspaceError
from app.platform.http_server import create_server
from app.platform.models import canonical, digest, input_object, label, project_identifier, revision_number
from app.platform.repository import SQLiteWorkspaceRepository
from app.platform.service import WorkspaceService


def report(payload):
    return {"summary": "Computed scenario", "metrics": [{"label": "Value", "value": payload.get("value", 1), "unit": "USD"}],
            "details": {"records": [payload]}, "evidence": ["Computed"], "next_actions": ["Review"]}


class WorkspaceContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "workspace.sqlite"
        self.repository = SQLiteWorkspaceRepository(self.database)
        self.calls = []
        def execute(project_id, payload, mode):
            self.calls.append((project_id, deepcopy(payload), mode))
            if payload.get("fail"):
                raise ValueError("Scenario is infeasible")
            return report(payload)
        self.service = WorkspaceService(self.repository, execute, lambda: {"product": SimpleNamespace(default_input=lambda: {"value": 1})})
        self.api = WorkspaceAPI(self.service)

    def tearDown(self):
        self.directory.cleanup()

    def scenario(self):
        return self.service.save_scenario("product", "Quarter end", {"value": 10})

    def execution(self, payload=None):
        return self.service.execute("product", payload or {"value": 10})

    def test_validated_json_is_detached_and_finite(self):
        original = {"nested": [1]}
        detached = input_object(original)
        detached["nested"].append(2)
        self.assertEqual(original, {"nested": [1]})
        for invalid in [[], None, {"value": float("nan")}, {"value": object()}, {"v": "x" * 262145}]:
            with self.subTest(invalid=type(invalid)), self.assertRaises(WorkspaceError):
                input_object(invalid)
        self.assertNotEqual(digest({"a": True}), digest({"a": 1}))
        self.assertEqual(digest({"b": 2, "a": 1}), digest({"a": 1, "b": 2}))

    def test_entity_text_and_revision_validation(self):
        self.assertEqual(label(" name ", "Name"), "name")
        self.assertEqual(project_identifier("product_1"), "product_1")
        for value in [None, "", "x" * 121]:
            with self.assertRaises(WorkspaceError): label(value, "Name")
        for value in [None, [], "../escape", "UPPER"]:
            with self.assertRaises(WorkspaceError): project_identifier(value)
        for value in [None, True, 0, 1.5]:
            with self.assertRaises(WorkspaceError): revision_number(value)

    def test_scenario_revisions_survive_repository_reopening(self):
        first = self.scenario()
        second = self.service.save_scenario("product", "Quarter end revised", {"value": 20}, first.scenario_id, 1)
        reopened = SQLiteWorkspaceRepository(self.database)
        self.assertEqual(reopened.get_scenario(first.scenario_id).payload, {"value": 20})
        self.assertEqual(reopened.get_scenario(first.scenario_id, 1).payload, {"value": 10})
        self.assertEqual(second.version, 2)
        self.assertEqual(reopened.list_scenarios("product")[0]["name"], "Quarter end revised")
        self.assertEqual(len(reopened.audit_events()), 2)

    def test_stale_update_does_not_add_a_revision_or_audit_event(self):
        first = self.scenario()
        self.service.save_scenario("product", "Revised", {"value": 2}, first.scenario_id, 1)
        with self.assertRaises(Conflict):
            self.service.save_scenario("product", "Stale", {}, first.scenario_id, 1)
        self.assertEqual(self.repository.get_scenario(first.scenario_id).version, 2)
        self.assertEqual(len(self.repository.audit_events()), 2)

    def test_parallel_revisions_have_exactly_one_winner(self):
        first = self.scenario()
        def save(value):
            try:
                return self.service.save_scenario("product", "Revision", {"value": value}, first.scenario_id, 1).version
            except Conflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, [20, 30]))
        self.assertEqual(results.count(2), 1)
        self.assertEqual(results.count("conflict"), 1)
        self.assertTrue(self.repository.verify_audit()["valid"])

    def test_missing_cross_project_and_invalid_scenario_commands(self):
        first = self.scenario()
        with self.assertRaises(NotFound): self.repository.get_scenario("missing")
        with self.assertRaises(NotFound): self.repository.get_scenario(first.scenario_id, 99)
        with self.assertRaises(NotFound): self.repository.save_scenario("product", "Missing", {}, "missing", 1)
        with self.assertRaises(Conflict): self.repository.save_scenario("different", "Wrong", {}, first.scenario_id, 1)
        with self.assertRaises(WorkspaceError): self.repository.save_scenario("product", "New", {}, expected_version=1)
        with self.assertRaises(WorkspaceError): self.service.save_scenario("unknown", "Invalid", {})

    def test_archiving_is_reversible_and_preserves_immutable_history(self):
        first = self.scenario()
        self.assertTrue(self.repository.archive_scenario(first.scenario_id, 1).archived)
        self.assertEqual(self.repository.list_scenarios("product"), [])
        self.assertEqual(len(self.repository.list_scenarios("product", True)), 1)
        with self.assertRaises(Conflict): self.service.execute("product", scenario_id=first.scenario_id, scenario_version=1)
        with self.assertRaises(Conflict): self.repository.save_scenario("product", "No", {}, first.scenario_id, 1)
        self.repository.archive_scenario(first.scenario_id, 1, False)
        self.repository.archive_scenario(first.scenario_id, 1, False)
        self.assertFalse(self.repository.get_scenario(first.scenario_id).archived)
        self.assertEqual(self.repository.verify_audit()["events_checked"], 3)
        with self.assertRaises(Conflict): self.repository.archive_scenario(first.scenario_id, 2)
        with self.assertRaises(NotFound): self.repository.archive_scenario("missing", 1)
        with self.assertRaises(WorkspaceError): self.repository.archive_scenario(first.scenario_id, 1, "yes")

    def test_run_pins_an_immutable_scenario_version(self):
        first = self.scenario()
        self.service.save_scenario("product", "Changed", {"value": 99}, first.scenario_id, 1)
        execution = self.service.execute("product", scenario_id=first.scenario_id, scenario_version=1)
        self.assertEqual(execution.payload, {"value": 10})
        self.assertEqual(execution.scenario_version, 1)
        self.assertEqual(execution.status, "succeeded")
        self.assertEqual(self.repository.get_execution(execution.run_id).report, report({"value": 10}))
        self.assertNotIn("payload", self.repository.list_executions("product")[0])

    def test_referenced_scenario_cannot_be_swapped(self):
        first = self.scenario()
        for arguments in [{"scenario_id": first.scenario_id}, {"scenario_version": 1}]:
            with self.assertRaises(WorkspaceError): self.service.execute("product", **arguments)
        with self.assertRaises(Conflict): self.service.execute("product", {"value": 999}, scenario_id=first.scenario_id, scenario_version=1)
        with self.assertRaises(Conflict): self.repository.reserve_execution("product", {}, scenario_id=first.scenario_id, scenario_version=1)
        with self.assertRaises(WorkspaceError): self.repository.reserve_execution("product", {}, scenario_id=first.scenario_id)

    def test_idempotent_retry_does_not_repeat_calculation(self):
        first = self.service.execute("product", {"value": 3}, idempotency_key="request-1")
        second = self.service.execute("product", {"value": 3}, idempotency_key="request-1")
        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(len(self.calls), 1)
        with self.assertRaises(Conflict): self.service.execute("product", {"value": 4}, idempotency_key="request-1")
        with self.assertRaises(Conflict): self.repository.reserve_execution("product", {"value": 3}, "live", idempotency_key="request-1")

    def test_parallel_reservation_returns_one_new_record(self):
        def reserve(_): return self.repository.reserve_execution("product", {}, idempotency_key="parallel")
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(reserve, range(4)))
        self.assertEqual(sum(created for _, created in outcomes), 1)
        self.assertEqual(len({record.run_id for record, _ in outcomes}), 1)

    def test_failed_run_is_retained_but_cannot_be_reviewed(self):
        failed = self.service.execute("product", {"fail": True})
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error, "Scenario is infeasible")
        with self.assertRaises(Conflict): self.repository.review_execution(failed.run_id, "approved", "Operator", "Reviewed", 0)
        self.assertEqual(self.repository.verify_audit()["events_checked"], 2)

    def test_unexpected_failure_records_sanitized_status_and_propagates(self):
        self.service.executor = lambda *args: (_ for _ in ()).throw(RuntimeError("private internal detail"))
        with self.assertRaises(RuntimeError): self.service.execute("product", {})
        row = self.repository.list_executions("product")[0]
        self.assertEqual(row["status"], "failed")
        self.assertNotIn("private internal detail", row["error"])

    def test_terminal_execution_evidence_cannot_be_overwritten(self):
        execution = self.execution()
        with self.assertRaises(Conflict): self.repository.finish_execution(execution.run_id, report=report({"value": 999}))
        with self.assertRaises(NotFound): self.repository.finish_execution("missing", error="Failed")
        with self.assertRaises(WorkspaceError): self.repository.finish_execution(execution.run_id)
        with self.assertRaises(WorkspaceError): self.repository.finish_execution(execution.run_id, report={}, error="Failed")
        with self.assertRaises(WorkspaceError): self.repository.finish_execution(execution.run_id, report=[])
        with self.assertRaises(NotFound): self.repository.get_execution("missing")

    def test_review_transition_requires_revision_rationale_and_successful_run(self):
        execution = self.execution()
        reviewed = self.repository.review_execution(execution.run_id, "approved", "Reviewer", "Checked the source evidence", 0)
        self.assertEqual((reviewed.review_status, reviewed.review_version), ("approved", 1))
        with self.assertRaises(Conflict): self.repository.review_execution(execution.run_id, "needs_changes", "Reviewer", "Stale", 0)
        with self.assertRaises(Conflict): self.repository.review_execution(execution.run_id, "rejected", "Reviewer", "Not permitted", 1)
        with self.assertRaises(WorkspaceError): self.repository.review_execution(execution.run_id, "needs_changes", "Reviewer", "", 1)
        self.repository.review_execution(execution.run_id, "needs_changes", "Reviewer", "New evidence found", 1)
        final = self.repository.review_execution(execution.run_id, "rejected", "Reviewer", "Threshold not met", 2)
        self.assertEqual(final.review_version, 3)
        with self.assertRaises(WorkspaceError): self.repository.review_execution(execution.run_id, "needs_changes", "Reviewer", "Note", True)
        with self.assertRaises(NotFound): self.repository.review_execution("missing", "approved", "Reviewer", "Note", 0)
        event = self.repository.audit_events()[0]
        self.assertEqual(event["details"]["report_sha256"], digest(execution.report))

    def test_audit_chain_detects_out_of_band_change(self):
        self.scenario(); self.execution()
        self.assertTrue(self.repository.verify_audit()["valid"])
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE audit_events SET details='{}' WHERE sequence=2")
        result = self.repository.verify_audit()
        self.assertFalse(result["valid"])
        self.assertEqual(result["first_invalid_sequence"], 2)

    def test_explicit_recovery_preserves_interrupted_records(self):
        execution, _ = self.repository.reserve_execution("product", {})
        with self.assertRaises(ValueError): workspace_command(self.database, "recover")
        result = workspace_command(self.database, "recover", acknowledge_no_active_runs=True)
        self.assertEqual(result["interrupted_runs"], 1)
        self.assertEqual(self.repository.get_execution(execution.run_id).status, "interrupted")
        self.assertEqual(self.repository.recover_interrupted(), 0)
        self.assertTrue(workspace_command(self.database, "inspect")["audit_integrity"]["valid"])
        self.assertEqual(len(workspace_command(self.database, "audit")["events"]), 2)
        with self.assertRaises(ValueError): workspace_command(self.database, "unknown")

    def test_newer_schema_is_not_downgraded(self):
        with closing(sqlite3.connect(self.database)) as connection, connection: connection.execute("PRAGMA user_version=999")
        with self.assertRaisesRegex(ValueError, "newer"): SQLiteWorkspaceRepository(self.database)

    def test_list_limits_and_invalid_modes(self):
        for value in [0, -1, 201, True, "10"]:
            for method in [lambda: self.repository.list_scenarios("product", limit=value), lambda: self.repository.list_executions("product", value), lambda: self.repository.audit_events(value)]:
                with self.assertRaises(WorkspaceError): method()
        with self.assertRaises(WorkspaceError): self.repository.reserve_execution("product", {}, "unknown")
        with self.assertRaises(WorkspaceError): WorkspaceService(self.repository, None, None, "unknown")

    def test_default_execution_uses_actual_application_defaults(self):
        record = self.service.execute("product")
        self.assertEqual(record.payload, {"value": 1})

    def test_run_comparison_preserves_units_and_input_types(self):
        left = self.execution({"value": 0.1, "same": True, "removed": "old"})
        right = self.execution({"value": 0.3, "same": 1, "added": "new"})
        comparison = self.service.compare(left.run_id, right.run_id)
        self.assertEqual(comparison["metrics"][0]["numeric_delta"], "0.2")
        self.assertEqual(len(comparison["input_changes"]), 4)
        self.assertFalse(comparison["input_changes_truncated"])
        self.assertEqual(self.service.compare(left.run_id, left.run_id)["input_changes"], [])

    def test_comparison_limits_and_rejects_incompatible_runs(self):
        left = self.execution({str(i): 0 for i in range(10)})
        right = self.execution({str(i): 1 for i in range(10)})
        result = RunComparisonService(2).compare(left, right)
        self.assertTrue(result["input_changes_truncated"])
        self.assertEqual(len(result["input_changes"]), 2)
        from dataclasses import replace
        with self.assertRaises(Conflict): RunComparisonService().compare(left, replace(right, project_id="other"))
        with self.assertRaises(Conflict): RunComparisonService().compare(left, replace(right, status="failed"))
        for limit in [0, 1001, True]:
            with self.assertRaises(ValueError): RunComparisonService(limit)
        for value in [None, True, [], "infinite", "NaN"]: self.assertIsNone(RunComparisonService._number(value))
        self.assertEqual(RunComparisonService._number("3.4"), Decimal("3.4"))
        self.assertEqual(len(RunComparisonService._metric_map([{"label": "x"}, {"label": "x"}])), 2)

    def test_api_resource_commands_use_shared_services(self):
        status, scenario = self.api.dispatch("POST", "/api/v1/scenarios", {"project_id": "product", "name": "Saved", "payload": {"value": 7}})
        self.assertEqual(status, 201)
        status, run = self.api.dispatch("POST", "/api/v1/executions", {"project_id": "product", "scenario_id": scenario["scenario_id"], "scenario_version": 1})
        self.assertEqual((status, run["status"]), (201, "succeeded"))
        self.assertEqual(self.api.dispatch("GET", "/api/v1/scenarios?project_id=product")[1]["items"][0]["version"], 1)
        self.assertEqual(self.api.dispatch("GET", "/api/v1/scenarios/" + scenario["scenario_id"] + "?version=1")[1]["payload"], {"value": 7})
        self.assertEqual(self.api.dispatch("GET", "/api/v1/executions/" + run["run_id"])[1]["status"], "succeeded")
        self.assertEqual(len(self.api.dispatch("GET", "/api/v1/executions?project_id=product")[1]["items"]), 1)
        self.assertTrue(self.api.dispatch("GET", "/api/v1/audit/integrity")[1]["valid"])
        self.assertEqual(self.api.dispatch("GET", "/api/v1/diagnostics")[1]["executions"], 1)
        self.assertEqual(len(self.api.dispatch("GET", "/api/v1/audit")[1]["items"]), 3)
        self.assertEqual(self.api.dispatch("GET", f"/api/v1/compare?left={run['run_id']}&right={run['run_id']}")[1]["input_changes"], [])
        self.assertEqual(self.api.dispatch("POST", f"/api/v1/executions/{run['run_id']}/review", {"decision": "approved", "reviewer": "Reviewer", "note": "Verified", "expected_version": 0})[0], 200)
        self.assertEqual(self.api.dispatch("POST", f"/api/v1/scenarios/{scenario['scenario_id']}/archive", {"expected_version": 1})[0], 200)

    def test_api_rejects_unknown_commands_duplicate_queries_and_stale_versions(self):
        for method, path, body, expected in [
            ("GET", "/api/unknown", None, 404), ("DELETE", "/api/v1/scenarios", None, 405),
            ("GET", "/api/v1/unknown", None, 404), ("POST", "/api/v1/unknown", {}, 404),
            ("GET", "/api/v1/scenarios?project_id=product&project_id=other", None, 400),
            ("GET", "/api/v1/scenarios?project_id=product&archived=yes", None, 400),
            ("GET", "/api/v1/scenarios?project_id=product&limit=oops", None, 400),
            ("GET", "/api/v1/executions/missing", None, 404),
            ("POST", "/api/v1/scenarios", {}, 400),
            ("POST", "/api/v1/scenarios", {"project_id": "product", "name": "A", "payload": {}, "extra": 1}, 400),
            ("POST", "/api/v1/executions/missing/review", {"decision": [], "reviewer": "R", "note": "N", "expected_version": 0}, 400),
        ]:
            with self.subTest(path=path): self.assertEqual(self.api.dispatch(method, path, body)[0], expected)
        scenario = self.scenario()
        self.repository.save_scenario("product", "Updated", {}, scenario.scenario_id, 1)
        self.assertEqual(self.api.dispatch("POST", f"/api/v1/scenarios/{scenario.scenario_id}/archive", {"expected_version": 1})[0], 409)


class WorkspaceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        (root / "static").mkdir(); (root / "static/index.html").write_text("<!doctype html><title>Product</title>")
        (root / "private.txt").write_text("Never public")
        (root / "static/outside.txt").symlink_to(root / "private.txt")
        repository = SQLiteWorkspaceRepository(root / "private/workspace.sqlite")
        self.service = WorkspaceService(repository, lambda pid, payload, mode: report(payload), lambda: {"product": SimpleNamespace(default_input=lambda: {})})
        self.token = "operator-token-" + "x" * 32
        self.server = create_server(root / "static", self.service, WorkspaceSettings(port=0, access_token=self.token))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(3); self.directory.cleanup()

    def request(self, path, method="GET", body=None, headers=None, authenticated=True):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        fields = {"Content-Type": "application/json"}
        if authenticated: fields["Authorization"] = "Bearer " + self.token
        fields.update(headers or {})
        if isinstance(body, dict): body = json.dumps(body)
        connection.request(method, path, body=body, headers=fields)
        response = connection.getresponse(); content = response.read(); connection.close()
        return response.status, content, dict(response.getheaders())

    def test_health_is_public_but_workspace_requires_token(self):
        status, body, _ = self.request("/api/health", authenticated=False)
        self.assertEqual(status, 200); self.assertTrue(json.loads(body)["authentication_required"])
        self.assertEqual(self.request("/api/v1/diagnostics", authenticated=False)[0], 401)
        self.assertEqual(self.request("/api/v1/diagnostics", headers={"Authorization": "Bearer wrong"})[0], 401)
        self.assertEqual(self.request("/api/v1/diagnostics")[0], 200)
        self.assertNotIn(self.token, repr(self.server.settings))

    def test_origin_host_content_type_and_body_controls(self):
        route = "/api/v1/executions"
        body = {"project_id": "product", "payload": {}}
        self.assertEqual(self.request(route, "POST", body, {"Origin": "https://attacker.invalid"})[0], 403)
        self.assertEqual(self.request(route, "POST", body, {"Host": "attacker.invalid"})[0], 403)
        self.assertEqual(self.request(route, "POST", body, {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request(route, "POST", "x" * 262145)[0], 413)
        self.assertEqual(self.request(route, "POST", "")[0], 413)
        self.assertEqual(self.request(route, "POST", "not-json")[0], 400)
        self.assertEqual(self.request(route, "POST", '{"value": NaN}')[0], 400)
        self.assertEqual(self.request(route, "POST", body, {"Transfer-Encoding": "chunked"})[0], 400)

    def test_http_persisted_run_can_be_retrieved_and_reviewed(self):
        status, body, headers = self.request("/api/v1/executions", "POST", {"project_id": "product", "payload": {"value": 3}})
        result = json.loads(body)
        self.assertEqual((status, result["status"]), (201, "succeeded"))
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.request("/api/v1/executions/" + result["run_id"])[0], 200)
        self.assertEqual(self.request("/api/v1/executions/" + result["run_id"] + "/review", "POST",
                                      {"decision": "approved", "reviewer": "Operator", "note": "Evidence inspected", "expected_version": 0})[0], 200)

    def test_static_files_cannot_read_outside_root_or_list_directories(self):
        self.assertEqual(self.request("/")[0], 200)
        self.assertEqual(self.request("/outside.txt")[0], 404)
        folder = Path(self.directory.name) / "static/empty"; folder.mkdir()
        self.assertEqual(self.request("/empty/")[0], 403)
        self.assertEqual(self.request("/api/missing")[0], 404)
        self.assertEqual(self.request("/missing", "POST", {})[0], 404)

    def test_legacy_run_endpoint_remains_compatible(self):
        self.assertEqual(self.request("/api/run", "POST", {"project_id": "product", "payload": {}})[0], 200)
        self.assertEqual(self.request("/api/run", "POST", {"unexpected": True})[0], 400)

    def test_capacity_exhaustion_returns_retryable_status(self):
        for _ in range(self.server.settings.maximum_requests): self.assertTrue(self.server._slots.acquire(False))
        try: self.assertEqual(self.request("/api/health")[0], 503)
        finally:
            for _ in range(self.server.settings.maximum_requests): self.server._slots.release()


class DeploymentPolicyTests(unittest.TestCase):
    def test_remote_binding_requires_token_and_exact_origin(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(WorkspaceSettings.from_environment().host, "127.0.0.1")
            with self.assertRaises(ValueError): WorkspaceSettings.from_environment("0.0.0.0")
        with patch.dict(os.environ, {"APP_ACCESS_TOKEN": "x" * 32, "APP_PUBLIC_ORIGIN": "https://workspace.example"}, clear=True):
            settings = WorkspaceSettings.from_environment("0.0.0.0")
            self.assertEqual(settings.origins(8765), {"https://workspace.example"})
        for origin in ["http://remote.example", "https://user:pass@example.com", "https://example.com/", "https://example.com?key=x", "file:///tmp/a", "https://example.com:invalid"]:
            with patch.dict(os.environ, {"APP_PUBLIC_ORIGIN": origin}, clear=True), self.assertRaises(ValueError): WorkspaceSettings.from_environment()
        for token in ["short", "x" * 4097, "x" * 31 + " "]:
            with patch.dict(os.environ, {"APP_ACCESS_TOKEN": token}, clear=True), self.assertRaises(ValueError): WorkspaceSettings.from_environment()
        for port in [-1, 65536, True]:
            with self.assertRaises(ValueError): WorkspaceSettings.from_environment(port=port)
