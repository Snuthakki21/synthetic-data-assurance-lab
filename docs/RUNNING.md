# Run and inspect the application

The Python application runs from a source checkout on Python 3.11 or later with the standard library. No API key, cloud account, database server or runtime package installation is required. The browser version uses the bundled Pyodide runtime; it is a separate WebAssembly runtime dependency, not a Python pip dependency. The source metadata in pyproject.toml describes this checkout; this repository does not publish an installable Python wheel.

## Local workspace

From the repository root:

```sh
python3 -m portfolio serve
```

Open http://127.0.0.1:8765. Choose an example, change the domain controls or JSON input, run the scenario and inspect/download the result. The server builds dist/ before starting, calculates results with the local Python process, and binds only to loopback. Stop it with Ctrl+C. Use `--port 8766` if the default port is busy. Restart after editing Python code because loaded project modules are cached for the running process.

## Command-line execution

```sh
python3 -m portfolio list
python3 -m portfolio run PROJECT_ID
python3 -m portfolio run PROJECT_ID --input scenario.json --output reports/result.json
```

Replace PROJECT_ID with the identifier printed by `list` in this repository. Omit `--input` to use the original synthetic default. The same validation and algorithms run through the CLI, browser worker and local server. Reports contain summary, metrics, evidence, next actions, full details and provenance: input/source hashes, mode, timing and model-call status. Timestamps and timing vary; a source hash identifies code/data, not a signed attestation. Results are written only when you request an output file or download.

Input must be a JSON object of at most 256 KB; each project has tighter domain limits. Invalid input produces a controlled CLI error (exit 2) or an API/browser error. Input imports and reviewer labels are scenario data, not authenticated identity. Original fixtures are fictional. Keep real confidential data out of public examples and exported reports.

## Static browser and GitHub Pages

```sh
python3 -m portfolio build --output dist
python3 -m http.server 8765 --bind 127.0.0.1 --directory dist
```

This static server provides no execution API. The browser loads the reviewed Python source from application.zip and runs local algorithms inside a worker. The application includes executed examples immediately; a fresh run loads WebAssembly and may take longer the first time. Serve over HTTP/HTTPS rather than opening index.html as a file. Browser runs have a two-minute timeout and can be canceled. Browser-only execution does not call a model provider or require a key. Network access is needed to load site assets on the first visit; offline caching is not guaranteed.

GitHub Pages serves the same static output. Configure the repository's Pages source as GitHub Actions. On main or manual dispatch, pages.yml calls the test workflow, waits for both Python versions and the coverage gate, then builds/uploads/deploys dist/. Only deployment has Pages write and OIDC token permissions. The exact action commits were resolved from official GitHub tags on 2026-09-17; see ACTION_PINS.md. A configured workflow is not proof of a successful hosted deployment: inspect the repository's Actions and Deployments results.

## Tests and coverage

```sh
python3 -m unittest discover -s tests -v
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m coverage run -m unittest discover -s tests -v
.venv/bin/python -m coverage report
```

On Windows use `.venv\Scripts\python.exe` for the virtual environment. The test-reporting dependency is pinned; runtime execution remains stdlib-only. Coverage measures statements and branches in portfolio/ and projects/ with a 90% minimum. Independent tests may explicitly skip a scenario for an application absent from a standalone export; a skip is not a successful execution. CI builds all included examples, then runs committed frontend test files via Node 24 when present. Live provider quality and production readiness are not inferred from test coverage.

## Troubleshooting

| Symptom | Action |
|---|---|
| Browser engine cannot start | Check asset loading and WebAssembly support, then use the Python local server if needed. |
| Run exceeds browser timeout | Reduce the input or use the local CLI within the documented project limits. |
| Changes are not reflected | Rebuild the site and restart the local process; refresh the page. |
| Unsupported question or input | Follow the project's documented vocabulary/schema; the system intentionally rejects unsupported cases. |
| Model call fails | Check explicit model, endpoint, timeout and output schema in MODEL_INTEGRATION.md; failures are not silently called successful. |
| Pages does not publish | Check test/coverage results and repository Pages settings before retrying deployment. |

Use the [model integration guide](MODEL_INTEGRATION.md) for optional AI and MCP. Read [SECURITY.md](../SECURITY.md) before changing the transport or data scope.
