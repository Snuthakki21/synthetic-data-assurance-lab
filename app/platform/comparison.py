"""Explain changes between immutable runs without attributing causality."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .errors import Conflict
from .models import ExecutionRecord, canonical


class RunComparisonService:
    def __init__(self, maximum_changes: int = 200):
        if type(maximum_changes) is not int or not 1 <= maximum_changes <= 1000:
            raise ValueError("Comparison limit must be from 1 to 1000.")
        self.maximum_changes = maximum_changes

    def compare(self, left: ExecutionRecord, right: ExecutionRecord) -> dict:
        if left.project_id != right.project_id:
            raise Conflict("Only runs from the same application can be compared.")
        if left.status != "succeeded" or right.status != "succeeded":
            raise Conflict("Both compared executions must have succeeded.")
        changes: list[dict] = []
        self._walk(left.payload, right.payload, "$", changes)
        left_metrics = self._metric_map(left.report.get("metrics", []))
        right_metrics = self._metric_map(right.report.get("metrics", []))
        metrics = []
        for key in sorted(left_metrics.keys() | right_metrics.keys()):
            before, after = left_metrics.get(key), right_metrics.get(key)
            delta = None
            if before is not None and after is not None:
                a, b = self._number(before.get("value")), self._number(after.get("value"))
                if a is not None and b is not None and before.get("unit", "") == after.get("unit", ""):
                    delta = str(b - a)
            metrics.append({"label": key, "before": before, "after": after, "numeric_delta": delta})
        return {"left_run_id": left.run_id, "right_run_id": right.run_id, "project_id": left.project_id,
                "input_changes": changes[:self.maximum_changes], "input_changes_truncated": len(changes) > self.maximum_changes,
                "metrics": metrics, "before_summary": left.report.get("summary", ""), "after_summary": right.report.get("summary", ""),
                "interpretation": "Observed differences between these inputs and runs; not a causal attribution or statistical significance claim."}

    @staticmethod
    def _metric_map(metrics: list) -> dict:
        result = {}
        reserved = {str(metric.get("label", f"Metric {index + 1}")) for index, metric in enumerate(metrics)}
        for index, metric in enumerate(metrics):
            name = str(metric.get("label", f"Metric {index + 1}"))
            if name in result:
                base, suffix = name, index + 1
                name = f"{base} [{suffix}]"
                while name in result or name in reserved:
                    suffix += 1
                    name = f"{base} [{suffix}]"
            result[name] = metric
        return result

    @staticmethod
    def _number(value: Any) -> Decimal | None:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return None
        try:
            number = Decimal(str(value))
            return number if number.is_finite() else None
        except InvalidOperation:
            return None

    def _walk(self, before: Any, after: Any, path: str, changes: list[dict]) -> None:
        if len(changes) > self.maximum_changes or canonical(before) == canonical(after):
            return
        if isinstance(before, dict) and isinstance(after, dict):
            for key in sorted(before.keys() | after.keys()):
                target = path + "[" + canonical(key) + "]"
                if key not in before:
                    changes.append({"path": target, "kind": "added", "after": after[key]})
                elif key not in after:
                    changes.append({"path": target, "kind": "removed", "before": before[key]})
                else:
                    self._walk(before[key], after[key], target, changes)
                if len(changes) > self.maximum_changes:
                    break
        else:
            changes.append({"path": path, "kind": "changed", "before": before, "after": after})
