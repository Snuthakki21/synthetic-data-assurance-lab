"""Explicit deployment policy for the native workspace API."""
from dataclasses import dataclass, field
import os
from urllib.parse import urlsplit


@dataclass(frozen=True)
class WorkspaceSettings:
    host: str = "127.0.0.1"
    port: int = 8765
    public_origin: str | None = None
    access_token: str | None = field(default=None, repr=False)
    maximum_requests: int = 8

    @classmethod
    def from_environment(cls, host: str = "127.0.0.1", port: int = 8765):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("Port must be between 0 and 65535.")
        if host == "::1":
            raise ValueError("Use the IPv4 loopback address 127.0.0.1 for this server.")
        token = os.environ.get("APP_ACCESS_TOKEN") or None
        origin = os.environ.get("APP_PUBLIC_ORIGIN") or None
        if token and (not 32 <= len(token) <= 4096 or any(c.isspace() for c in token)):
            raise ValueError("APP_ACCESS_TOKEN must be 32–4,096 characters without whitespace.")
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise ValueError("APP_PUBLIC_ORIGIN must be an exact HTTP(S) origin without path or credentials.")
            if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("A remote public origin requires HTTPS at the trusted reverse proxy.")
            try:
                parsed.port
            except ValueError as error:
                raise ValueError("Public origin has an invalid port.") from error
        if host not in {"127.0.0.1", "localhost", "::1"} and (not token or not origin):
            raise ValueError("Non-loopback binding requires APP_ACCESS_TOKEN and APP_PUBLIC_ORIGIN.")
        return cls(host, port, origin, token)

    def origins(self, actual_port: int) -> set[str]:
        if self.public_origin:
            return {self.public_origin}
        return {f"http://127.0.0.1:{actual_port}", f"http://localhost:{actual_port}"}
