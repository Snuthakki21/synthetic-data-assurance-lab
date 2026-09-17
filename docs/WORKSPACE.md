# Workspace lifecycle and operating guide

The application has two storage modes. GitHub Pages executes the same Python source in a browser worker and saves scenarios, results and review records in IndexedDB. The native server executes Python directly and commits records to SQLite. No account or network service is required for browser computation. Optional live model calls require native execution and explicit provider configuration.

## A reproducible decision workflow

1. Open an example, adjust its domain controls or load JSON, and execute it.
2. In **Scenario library**, name and save the exact input. Load any retained revision. **Save next revision** succeeds only when the selected revision is still current.
3. Execute the saved input. A matching saved revision is attached to the execution; editing its values creates an unbound run until you save a new scenario revision.
4. In **Execution history**, inspect the exact input/result pair. Review the evidence with a rationale and operator identifier. A review applies to this immutable run, not future runs or production permissions.
5. Compare two successful runs. Metric differences preserve decimal values and compatible units. Changed inputs explain the comparison context; differences are not causal proof.
6. Export important records. Archiving a scenario retains its revisions and execution history; restoring it enables new work.

A successful run begins unreviewed. It may become approved, needs changes, or rejected. Approved/rejected records may return to needs changes; a needs-changes review may become approved or rejected. Every review uses an expected review version, preventing stale decisions from silently overwriting each other.

## Browser persistence

Data is isolated by product and browser origin. Closing the page preserves committed records; clearing site data removes them. Browser records are editable by the browser user and unsigned. They are not a cloud account, compliance archive or authenticated multi-user audit trail. The library supports 500 scenarios with 500 revisions each and 1,000 executions. Complete workspace export includes all retained browser revisions, runs and audit events. Only the newest 100 executions are shown in the history table. Storage errors are displayed without discarding a computed report; download that report before leaving.

## Native server

```sh
python -m portfolio serve --port 8765 --database var/workspace.sqlite
```

The default listener is IPv4 loopback. The database is created with owner-only file permissions. Inputs are limited to 256 KB and reports to 16 MB. Up to eight HTTP requests are serviced concurrently; excess work receives 503 with Retry-After. Request bodies time out after 15 seconds. Calculations and provider calls happen outside write transactions, while revisions, run reservations and audit events use atomic transactions. Idempotency keys prevent duplicate execution of an identical submitted request.

The default interface is a single-operator application. Non-loopback binding requires `APP_ACCESS_TOKEN` (32–4,096 non-whitespace characters) and `APP_PUBLIC_ORIGIN`. Remote public origins require HTTPS at a trusted reverse proxy. The browser asks for the token in Scenario library, retains it only in tab memory and sends it in the Authorization header. Host and Origin must match the configured origin. Reviewer identifiers are labels, not individual authenticated accounts; bearer access grants access to the entire workspace. Use an identity-aware gateway and organizational controls before a multi-user deployment.

```sh
python -m portfolio workspace inspect --database var/workspace.sqlite
python -m portfolio workspace audit --database var/workspace.sqlite
python -m portfolio workspace backup --database var/workspace.sqlite --output backups/workspace.sqlite
```

Backup uses SQLite's consistent online backup API, includes all history and never overwrites a target. Protect exported files as carefully as the source inputs. Restore with all application processes stopped: preserve the current database, place the verified backup at the configured database path, run `workspace inspect`, and start the server. Do not restore over an active SQLite connection.

After a crash, stop all servers using that database, then run:

```sh
python -m portfolio workspace recover --database var/workspace.sqlite --acknowledge-no-active-runs
```

Recovery marks unfinished runs interrupted without inventing results. It never automatically replays model requests. Start a new execution explicitly. Automatic recovery is deliberately avoided because another server might still own an active run.

The audit hash chain detects inconsistent stored events; it does not prevent an administrator from rewriting the database. Keep independently protected backup checkpoints when you need stronger evidence retention. Schema version 1 is initialized transactionally. A future schema version is rejected rather than silently downgraded.

## Container and installation

`docker compose up --build` runs a non-root application with a persistent volume and loopback host port. Set your own access token first; the sample environment file contains no credential. For an external deployment, put a trusted HTTPS reverse proxy in front, preserve the configured Host, set the exact public origin, and restrict database volume access. A generated container recipe is not a claim of tested cloud deployment.

Install one application per virtual environment; each repository is a separate distribution with its own `app`, `projects`, `portfolio` runtime and bundled `web` assets:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install .
application run
application serve
```

The historical `portfolio` Python command is retained as a compatibility entry point; it does not load or display an aggregate portfolio. Each distribution contains one product. Asset packaging follows [setuptools package data](https://setuptools.pypa.io/en/latest/userguide/datafiles.html) and namespace discovery. Runtime computations use the Python standard library.
