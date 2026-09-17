"""Loopback-only development server with a bounded JSON execution API."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlparse
from .registry import ROOT, execute


class Handler(SimpleHTTPRequestHandler):
    server_version = "PortfolioDemo/1.0"

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def respond(self, status, value):
        raw = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/api/health":
            self.respond(200, {"status": "ready", "mode": self.server.run_mode})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path != "/api/run":
            return self.respond(404, {"error": "Unknown endpoint"})
        host = self.headers.get("Host", "")
        expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        origin = self.headers.get("Origin")
        if host not in expected or (origin and origin not in {f"http://{x}" for x in expected}):
            return self.respond(403, {"error": "Only same-origin loopback requests are accepted"})
        if self.headers.get_content_type() != "application/json":
            return self.respond(415, {"error": "Use application/json"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 262144:
                return self.respond(413, {"error": "Request must be 1 byte to 256 KB"})
            data = json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
            if not isinstance(data, dict) or set(data) - {"project_id", "payload"}:
                raise ValueError("Expected project_id and optional payload")
            result = execute(data.get("project_id"), data.get("payload"), mode=self.server.run_mode)
            self.respond(200, result)
        except (ValueError, TypeError, KeyError) as exc:
            self.respond(400, {"error": str(exc)[:300]})


def serve(port=8765, mode="local"):
    handler = partial(Handler, directory=str(ROOT / "dist"))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.run_mode = mode
    print(f"Open http://127.0.0.1:{server.server_port} ({mode} mode)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
