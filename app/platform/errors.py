"""Explicit application failures that transport adapters can safely expose."""


class WorkspaceError(ValueError):
    """An invalid workspace command."""


class NotFound(WorkspaceError):
    """The requested entity or immutable revision does not exist."""


class Conflict(WorkspaceError):
    """The caller's revision or idempotency expectation is stale."""
