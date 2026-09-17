"""Discover installed projects; works in an individual repo or the collection."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from .runtime import Context

ROOT = Path(__file__).resolve().parent.parent


def projects():
    result = {}
    for path in sorted((ROOT / "projects").glob("*/project.py")):
        module_name = "portfolio_project_" + path.parent.name
        module = sys.modules.get(module_name)
        if module is None:
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        if module.META["id"] != path.parent.name:
            raise ValueError("Project id does not match directory")
        result[module.META["id"]] = module
    return dict(sorted(result.items(), key=lambda item: item[1].META["order"]))


def source_digest():
    digest = hashlib.sha256()
    for folder in ("portfolio", "projects"):
        for file in sorted((ROOT / folder).rglob("*")):
            if file.is_file() and file.suffix in {".py", ".json", ".csv", ".sql", ".cbl", ".cpy", ".txt"}:
                digest.update(str(file.relative_to(ROOT)).encode())
                digest.update(file.read_bytes())
    return digest.hexdigest()


def execute(project_id, payload=None, mode="local"):
    if not isinstance(project_id, str):
        raise ValueError("Project identifier must be text")
    module = projects().get(project_id)
    if module is None:
        raise ValueError("Unknown project")
    payload = module.default_input() if payload is None else payload
    if not isinstance(payload, dict):
        raise ValueError("Input must be a JSON object")
    encoded = json.dumps(payload, sort_keys=True, allow_nan=False).encode()
    if len(encoded) > 262144:
        raise ValueError("Input exceeds 256 KB limit")
    # Release evaluation calls the candidate once per case; preflight before any provider call.
    call_budget = 3
    if mode == "live" and project_id == "ai_release_gate":
        cases = payload.get("cases", [])
        if not isinstance(cases, list) or not 2 <= len(cases) <= 20:
            raise ValueError("Live evaluation requires 2 to 20 cases; no provider calls were made")
        call_budget = len(cases)
    context = Context(mode=mode, max_calls=call_budget)
    started = time.perf_counter()
    result = module.run(payload, context)
    elapsed = (time.perf_counter() - started) * 1000
    if not isinstance(result, dict) or not all(key in result for key in ("summary", "metrics", "evidence", "next_actions", "details")):
        raise ValueError("Project returned an invalid report")
    result["provenance"] = {
        "project_id": project_id, "executed_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode, "model_calls": context.calls,
        "elapsed_ms": round(elapsed, 3), "input_sha256": hashlib.sha256(encoded).hexdigest(),
        "source_sha256": source_digest(), "data_classification": "user supplied input" if payload != module.default_input() else "original synthetic fixture",
        "scope": "Reference application run; not a production benchmark or employer result",
    }
    json.dumps(result, allow_nan=False)
    return result
