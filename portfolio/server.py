"""Native application server with persistent runs and explicit deployment policy."""
from functools import partial
from pathlib import Path
from app.platform.api import WorkspaceAPI
from app.platform.config import WorkspaceSettings
from app.platform.http_server import WorkspaceHTTPServer, WorkspaceRequestHandler
from app.platform.repository import SQLiteWorkspaceRepository
from app.platform.service import WorkspaceService
from .registry import ROOT, execute, projects

ThreadingHTTPServer = WorkspaceHTTPServer


class Handler(WorkspaceRequestHandler):
    def execute(self, project_id, payload, mode):
        return execute(project_id, payload, mode=mode)


def serve(port=8765, mode="local", *, host="127.0.0.1", database=None):
    settings = WorkspaceSettings.from_environment(host, port)
    repository = SQLiteWorkspaceRepository(database or Path.cwd() / "var" / "workspace.sqlite")
    service = WorkspaceService(repository, execute, projects, mode)
    handler = partial(Handler, directory=str(ROOT / "dist"))
    server = ThreadingHTTPServer((host, port), handler, settings)
    server.run_mode = mode
    server.executor = execute
    server.workspace_api = WorkspaceAPI(service)
    print(f"Open {settings.public_origin or f'http://{host}:{server.server_port}'} ({mode} mode)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
