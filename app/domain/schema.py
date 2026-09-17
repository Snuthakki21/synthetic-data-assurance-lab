"""Schema domain policies and services."""


from datetime import date

from decimal import Decimal, InvalidOperation

import math


import re


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Decimal values must be finite numbers or numeric strings.")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal value.") from exc
    if not result.is_finite() or result.copy_abs() > Decimal("1000000000000"):
        raise ValueError("Decimal values must be finite and within +/- 1 trillion.")
    return result


def _has_scale(number, scale):
    """Check discarded digits without Decimal context rounding."""
    digits = number.as_tuple().digits
    discarded = number.as_tuple().exponent + scale
    return discarded >= 0 or all(digit == 0 for digit in digits[discarded:])


class RecipeValidator:
    def validate(self, payload):
        if not isinstance(payload, dict) or not _integer(payload.get("seed", 41)):
            raise ValueError("Input must be an object and seed must be an integer.")
        rules, counts = payload.get("rules"), payload.get("row_counts")
        if not isinstance(rules, dict) or not isinstance(rules.get("version"), str) or not rules["version"].strip():
            raise ValueError("A named, versioned rules object is required.")
        tables = rules.get("tables")
        if not isinstance(tables, list) or not 1 <= len(tables) <= 12 or not isinstance(counts, dict):
            raise ValueError("Provide 1–12 tables and row_counts.")
        named = {}
        for table in tables:
            if not isinstance(table, dict):
                raise ValueError("Each table must be an object.")
            name = table.get("name")
            if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name) or name in named:
                raise ValueError("Table names must be unique lowercase identifiers.")
            count = counts.get(name)
            if not _integer(count) or not 1 <= count <= 25000:
                raise ValueError("Each table needs 1–25,000 rows.")
            cols = table.get("columns")
            if not isinstance(cols, list) or not 1 <= len(cols) <= 32:
                raise ValueError("Each table needs 1–32 columns.")
            seen = set()
            for col in cols:
                if not isinstance(col, dict):
                    raise ValueError("Columns must be objects.")
                cname = col.get("name")
                if not isinstance(cname, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", cname) or cname in seen:
                    raise ValueError("Column names must be unique lowercase identifiers.")
                seen.add(cname)
                kind = col.get("type")
                if not isinstance(kind, str) or kind not in {"integer", "decimal", "enum", "date"}:
                    raise ValueError("Supported types: integer, decimal, enum, date.")
                nullable, null_rate = col.get("nullable", False), col.get("null_rate", 0)
                if not isinstance(nullable, bool) or isinstance(null_rate, bool) or not isinstance(null_rate, (int, float)) or not math.isfinite(null_rate) or not 0 <= null_rate <= 1 or (null_rate and not nullable):
                    raise ValueError("null_rate must be 0–1 and nonzero only for nullable columns.")
                if kind == "integer":
                    if not _integer(col.get("min")) or not _integer(col.get("max")) or not -10**12 <= col["min"] <= col["max"] <= 10**12:
                        raise ValueError("Integer bounds must be ordered integers within +/- 1 trillion.")
                elif kind == "decimal":
                    scale = col.get("scale")
                    if not _integer(scale) or not 0 <= scale <= 6:
                        raise ValueError("Decimal scale must be an integer from 0 to 6.")
                    lo, hi = _decimal(col.get("min")), _decimal(col.get("max"))
                    if lo > hi or any(not _has_scale(x, scale) for x in (lo, hi)):
                        raise ValueError("Decimal bounds must be ordered and exactly representable at scale.")
                elif kind == "date":
                    try:
                        lo, hi = date.fromisoformat(col.get("min", "")), date.fromisoformat(col.get("max", ""))
                    except (ValueError, TypeError) as exc:
                        raise ValueError("Date bounds must be ISO dates.") from exc
                    if lo > hi:
                        raise ValueError("Date bounds must be ordered.")
                else:
                    values, weights = col.get("values"), col.get("weights")
                    if not isinstance(values, list) or not 1 <= len(values) <= 100 or any(not isinstance(x, str) or not x or len(x) > 100 for x in values) or len(set(values)) != len(values):
                        raise ValueError("Enum values must be 1–100 unique nonempty strings.")
                    if weights is not None and (not isinstance(weights, list) or len(weights) != len(values) or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in weights) or not math.isfinite(sum(weights))):
                        raise ValueError("Enum weights must be finite positive values matching the domain.")
            primary = next((c for c in cols if c["name"] == table.get("primary_key")), None)
            if not primary or primary["type"] != "integer" or primary.get("nullable") or primary.get("references") or primary["max"] - primary["min"] + 1 < count:
                raise ValueError("Primary keys must be independent nonnullable integers with enough unique values.")
            named[name] = table
        if set(counts) != set(named) or sum(counts.values()) > 50000:
            raise ValueError("row_counts must match tables and total at most 50,000 rows.")
        dependencies = {name: set() for name in named}
        for name, table in named.items():
            for col in table["columns"]:
                ref = col.get("references")
                if ref is not None:
                    if not isinstance(ref, str) or len(ref.split(".")) != 2:
                        raise ValueError("references must name table.primary_key.")
                    target, key = ref.split(".")
                    if target not in named or key != named[target]["primary_key"] or col["type"] != "integer":
                        raise ValueError("Foreign keys must reference a declared integer primary key.")
                    pk = next(c for c in named[target]["columns"] if c["name"] == key)
                    if col["min"] > pk["min"] or col["max"] < pk["min"] + counts[target] - 1:
                        raise ValueError("Foreign key bounds must contain every generated parent key.")
                    dependencies[name].add(target)
        order = []
        while len(order) < len(named):
            ready = [name for name in named if name not in order and dependencies[name] <= set(order)]
            if not ready:
                raise ValueError("Cyclic or self-referencing generation dependencies are unsupported.")
            order.extend(ready)
        overrides = payload.get("audit_overrides", [])
        if not isinstance(overrides, list) or len(overrides) > 100:
            raise ValueError("audit_overrides must contain at most 100 targeted validation probes.")
        for item in overrides:
            if not isinstance(item, dict) or not isinstance(item.get("table"), str) or item.get("table") not in named or not _integer(item.get("row")) or not 0 <= item["row"] < counts[item["table"]] or not isinstance(item.get("column"), str) or item.get("column") not in {c["name"] for c in named[item["table"]]["columns"]} or "value" not in item or isinstance(item["value"], (dict, list)):
                raise ValueError("Each probe needs an existing table, zero-based row, column and scalar value.")
            if isinstance(item["value"], float) and not math.isfinite(item["value"]):
                raise ValueError("Probe numbers must be finite.")
        return named, order


_validate_recipe = RecipeValidator().validate
