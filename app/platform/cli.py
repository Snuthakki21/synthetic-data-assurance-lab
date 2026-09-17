"""Workspace inspection, consistent SQLite backups and explicit crash recovery."""
from pathlib import Path
from contextlib import closing
import os
import sqlite3
from .repository import SQLiteWorkspaceRepository


def workspace_command(database, operation, *, acknowledge_no_active_runs=False, output=None):
    if not Path(database).is_file():
        raise ValueError("Workspace database does not exist; start the application first.")
    repository = SQLiteWorkspaceRepository(database)
    if operation == "inspect":
        return {**repository.diagnostics(), "audit_integrity": repository.verify_audit()}
    if operation == "audit":
        return {"integrity": repository.verify_audit(), "events": repository.audit_events(200)}
    if operation == "recover":
        if not acknowledge_no_active_runs:
            raise ValueError("Recovery requires --acknowledge-no-active-runs after stopping all application servers.")
        return {"interrupted_runs": repository.recover_interrupted()}
    if operation == "backup":
        if output is None:
            raise ValueError("Backup requires --output and never overwrites an existing file.")
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        try:
            with closing(sqlite3.connect(database)) as origin, closing(sqlite3.connect(target)) as destination:
                origin.backup(destination)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return {"backup": str(target), "bytes": target.stat().st_size}
    raise ValueError("Unknown workspace operation.")
