# Native workspace API

API version: `/api/v1`. JSON only. API errors use `{ "error": "description" }`. Validation returns 400, missing records 404, stale versions/incompatible transitions 409, wrong Host/Origin 403 and invalid bearer access 401. The server rejects non-finite JSON, chunked bodies and requests above 256 KB. Cross-origin requests are not enabled.

| Method and route | Request | Result |
|---|---|---|
| GET `/api/health` | No credential | Mode, version, workspace availability and whether authentication is required; no data or secrets |
| POST `/api/v1/scenarios` | `project_id`, `name`, `payload`; optional `scenario_id`, `expected_version` | Immutable saved revision with input hash |
| GET `/api/v1/scenarios?project_id=ID&archived=false&limit=100` | Limit 1–200 | Current scenario headers |
| GET `/api/v1/scenarios/ID?version=1` | Optional exact revision | Saved input and archive state |
| POST `/api/v1/scenarios/ID/archive` | `expected_version`, `archived` boolean | Archived/restored scenario |
| POST `/api/v1/executions` | `project_id`, optional `payload`, optional `scenario_id` + `scenario_version`, optional `idempotency_key` | Stored terminal run (or existing reservation on an identical retry) |
| GET `/api/v1/executions?project_id=ID&limit=100` | Limit 1–200 | Recent run headers |
| GET `/api/v1/executions/ID` | — | Exact input/result/status/review |
| POST `/api/v1/executions/ID/review` | `decision`, `reviewer`, `note`, `expected_version` | Versioned evidence review |
| GET `/api/v1/compare?left=ID&right=ID` | Two successful runs of this application | Metric differences and changed inputs |
| GET `/api/v1/audit?limit=100` | Limit 1–200 | Recent audit events |
| GET `/api/v1/audit/integrity` | — | Chain verification result |
| GET `/api/v1/diagnostics` | — | Storage schema, counts and supported mode |

Get the installed application identifier with `python -m portfolio list`. Runs bound to a saved scenario must use an exact retained revision and identical input. Archived scenarios cannot create new runs. Reusing an idempotency key with different input, mode or revision returns 409. A completed failed run is evidence and is never overwritten by a retry; use a new key after correcting the input.

`POST /api/run` remains a stateless compatibility endpoint with the same input and origin controls. The application interface uses the versioned execution endpoint so its native runs are retained. The CLI `run` command writes a report; it does not create workspace history.

The native interface export contains current scenario revisions and the latest 100 runs. Use `workspace backup` for complete SQLite history. API pagination is intentionally bounded; the maintenance backup is the full-retention path.
