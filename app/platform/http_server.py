"""Bounded HTTP server; static assets and authenticated optional workspace API."""
from functools import partial
import hmac
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from socketserver import TCPServer
from urllib.parse import urlsplit

from .api import WorkspaceAPI
from .config import WorkspaceSettings


class WorkspaceHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, settings: WorkspaceSettings | None = None):
        super().__init__(address, handler)
        self.settings = settings or WorkspaceSettings()
        self._slots = threading.BoundedSemaphore(self.settings.maximum_requests)

    def server_bind(self):
        # Binding an explicit address must not wait on host reverse DNS.
        TCPServer.server_bind(self)
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\nRetry-After: 1\r\n\r\n")
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class WorkspaceRequestHandler(SimpleHTTPRequestHandler):
    server_version = "WorkspaceApplication/2.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/api/") else "no-cache")
        super().end_headers()

    def respond(self, status, value):
        raw = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass  # The stored execution remains available after client cancellation.

    def _authorize(self):
        settings = getattr(self.server, "settings", WorkspaceSettings())
        origins = settings.origins(self.server.server_port)
        hosts = {urlsplit(origin).netloc for origin in origins}
        host, origin = self.headers.get("Host", ""), self.headers.get("Origin")
        if host not in hosts or (origin and origin not in origins):
            self.respond(403, {"error": "Only same-origin loopback requests or the configured public origin are accepted"})
            return False
        if settings.access_token:
            credential = self.headers.get("Authorization", "")
            expected = "Bearer " + settings.access_token
            if not hmac.compare_digest(credential.encode(), expected.encode()):
                self.respond(401, {"error": "A valid workspace access token is required."})
                return False
        return True

    def do_GET(self):
        if self.path == "/api/health":
            settings = getattr(self.server, "settings", WorkspaceSettings())
            return self.respond(200, {"status": "ready", "mode": self.server.run_mode, "version": "2.0.0",
                                      "workspace": hasattr(self.server, "workspace_api"),
                                      "authentication_required": bool(settings.access_token)})
        if self.path.startswith("/api/"):
            if not self._authorize():
                return
            api = getattr(self.server, "workspace_api", None)
            status, value = api.dispatch("GET", self.path) if api else (404, {"error": "Workspace API unavailable."})
            return self.respond(status, value)
        return super().do_GET()

    def send_head(self):
        resolved = Path(self.translate_path(self.path)).resolve()
        if not resolved.is_relative_to(Path(self.directory).resolve()):
            return self.send_error(404)
        return super().send_head()

    def list_directory(self, path):
        self.send_error(403, "Directory listing is disabled.")
        return None

    def execute(self, project_id, payload, mode):
        return self.server.executor(project_id, payload, mode)

    def do_POST(self):
        if self.path != "/api/run" and not self.path.startswith("/api/v1/"):
            return self.respond(404, {"error": "Unknown endpoint"})
        if not self._authorize():
            return
        if self.headers.get_content_type() != "application/json":
            return self.respond(415, {"error": "Use application/json"})
        if self.headers.get("Transfer-Encoding"):
            return self.respond(400, {"error": "Chunked request bodies are not supported."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 262144:
                return self.respond(413, {"error": "Request must be 1 byte to 256 KB"})
            raw = self.rfile.read(size)
            if len(raw) != size:
                return self.respond(400, {"error": "Incomplete request body."})
            data = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
            if self.path == "/api/run":
                if not isinstance(data, dict) or set(data) - {"project_id", "payload"}:
                    raise ValueError("Expected project_id and optional payload")
                result = self.execute(data.get("project_id"), data.get("payload"), mode=self.server.run_mode)
                return self.respond(200, result)
            api = getattr(self.server, "workspace_api", None)
            status, value = api.dispatch("POST", self.path, data) if api else (404, {"error": "Workspace API unavailable."})
            return self.respond(status, value)
        except TimeoutError:
            return self.respond(408, {"error": "Request body timed out."})
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            return self.respond(400, {"error": str(error)[:300]})
        except Exception:
            self.log_error("Unexpected request failure; run history retains execution status")
            return self.respond(500, {"error": "Application failure. Inspect local logs and run history."})


def create_server(directory: Path, service, settings: WorkspaceSettings):
    handler = partial(WorkspaceRequestHandler, directory=str(directory))
    server = WorkspaceHTTPServer((settings.host, settings.port), handler, settings)
    server.run_mode = service.mode
    server.executor = service.executor
    server.workspace_api = WorkspaceAPI(service)
    return server
