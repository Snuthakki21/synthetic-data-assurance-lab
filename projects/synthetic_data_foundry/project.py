"""Seeded relational synthetic data with an independent integrity audit."""
from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import math
import random
import re
from time import perf_counter

DEFAULT = {
    "seed": 41, "row_counts": {"customers": 40, "orders": 200},
    "rules": {"version": "original-commerce-v1", "tables": [
        {"name": "customers", "primary_key": "customer_id", "columns": [
            {"name": "customer_id", "type": "integer", "min": 1001, "max": 999999},
            {"name": "segment", "type": "enum", "values": ["small_business", "enterprise", "consumer"], "weights": [0.35, 0.25, 0.4]},
            {"name": "joined_on", "type": "date", "min": "2025-01-01", "max": "2025-12-31"}]},
        {"name": "orders", "primary_key": "order_id", "columns": [
            {"name": "order_id", "type": "integer", "min": 1, "max": 999999},
            {"name": "customer_id", "type": "integer", "min": 1001, "max": 999999, "references": "customers.customer_id"},
            {"name": "amount", "type": "decimal", "min": "0.00", "max": "5000.00", "scale": 2},
            {"name": "status", "type": "enum", "values": ["pending", "paid", "refunded"], "weights": [0.15, 0.8, 0.05]}]}]},
    "audit_overrides": [], "rule_request": "Propose a narrower order amount range for boundary testing within the existing rules."}


def default_input():
    return deepcopy(DEFAULT)


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


def _validate_recipe(payload):
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


def _generate(named, order, counts, seed):
    # ponytail: keep fixtures in memory up to 50,000 rows; stream batches for larger workloads.
    rng, records = random.Random(seed), {}
    for name in order:
        table, rows = named[name], []
        for index in range(counts[name]):
            row = {}
            for col in table["columns"]:
                kind = col["type"]
                if col["name"] == table["primary_key"]:
                    value = col["min"] + index
                elif col.get("null_rate", 0) and rng.random() < col["null_rate"]:
                    value = None
                elif col.get("references"):
                    target, key = col["references"].split(".")
                    value = rng.choice(records[target])[key]
                elif kind == "integer":
                    value = rng.randint(col["min"], col["max"])
                elif kind == "decimal":
                    scale = col["scale"]
                    units = rng.randint(int(_decimal(col["min"]) * 10 ** scale), int(_decimal(col["max"]) * 10 ** scale))
                    value = format(Decimal(units) / 10 ** scale, f".{scale}f")
                elif kind == "enum":
                    value = rng.choices(col["values"], weights=col.get("weights"), k=1)[0]
                else:
                    first, last = date.fromisoformat(col["min"]), date.fromisoformat(col["max"])
                    value = (first + timedelta(days=rng.randint(0, (last - first).days))).isoformat()
                row[col["name"]] = value
            rows.append(row)
        records[name] = rows
    return records


def _domain_error(value, col):
    if value is None:
        return None if col.get("nullable", False) else "required value is null"
    kind = col["type"]
    if kind == "integer":
        return None if _integer(value) and col["min"] <= value <= col["max"] else "integer type or boundary violation"
    if kind == "enum":
        return None if value in col["values"] else "value outside enum domain"
    if kind == "decimal":
        try:
            number = _decimal(value)
            valid = _decimal(col["min"]) <= number <= _decimal(col["max"]) and _has_scale(number, col["scale"])
        except ValueError:
            valid = False
        return None if valid else "decimal precision or boundary violation"
    try:
        value_date = date.fromisoformat(value)
        valid = date.fromisoformat(col["min"]) <= value_date <= date.fromisoformat(col["max"])
    except (TypeError, ValueError):
        valid = False
    return None if valid else "invalid date or date outside boundary"


def audit(records, tables):
    """Audit values independently; keep all error counts but bound evidence size."""
    errors, total, checks = [], 0, 0
    parents = {(t["name"], t["primary_key"]): {r[t["primary_key"]] for r in records[t["name"]]} for t in tables.values()}
    for name, table in tables.items():
        seen = set()
        for index, row in enumerate(records[name]):
            problems = []
            for col in table["columns"]:
                value = row[col["name"]]
                checks += 1
                message = _domain_error(value, col)
                if message:
                    problems.append((col["name"], message))
                if col.get("references") and value is not None:
                    checks += 1
                    if value not in parents[tuple(col["references"].split("."))]:
                        problems.append((col["name"], "foreign key has no parent"))
            pk = table["primary_key"]
            checks += 1
            if row[pk] in seen:
                problems.append((pk, "duplicate primary key"))
            seen.add(row[pk])
            total += len(problems)
            errors.extend({"table": name, "row": index, "column": column, "reason": message} for column, message in problems[:max(0, 200 - len(errors))])
    return {"checks": checks, "issue_count": total, "issues": errors, "issues_truncated": total > len(errors)}


def _proposal(payload, named, context):
    request = payload.get("rule_request", "")
    if not isinstance(request, str) or len(request) > 2000:
        raise ValueError("rule_request must be a string of at most 2,000 characters.")
    if not request or context is None:
        return {"status": "not_requested" if not request else "local_mode_no_model_proposal"}
    numeric = {f"{name}.{c['name']}": c for name, table in named.items() for c in table["columns"] if c["type"] in {"integer", "decimal"} and c["name"] != table["primary_key"] and not c.get("references")}
    if not numeric:
        raise ValueError("Rule proposals require an independent numeric column.")
    schema = {"type": "object", "properties": {"column": {"type": "string", "enum": list(numeric)}, "minimum": {"type": "number"}, "maximum": {"type": "number"}, "rationale": {"type": "string"}}, "required": ["column", "minimum", "maximum", "rationale"], "additionalProperties": False}
    proposal = context.generate_json(task="Propose a narrower numeric generation range. Select a supplied column, preserve precision, keep bounds inside the versioned rules. This is for human review and will not be applied.", data={"request": request, "allowed_columns": numeric}, schema=schema)
    if proposal is None:
        return {"status": "local_mode_no_model_proposal"}
    if not isinstance(proposal, dict) or set(proposal) != {"column", "minimum", "maximum", "rationale"} or not isinstance(proposal.get("column"), str) or proposal.get("column") not in numeric or not isinstance(proposal.get("rationale"), str):
        raise ValueError("Model rule proposal failed structure or column validation.")
    col = numeric[proposal["column"]]
    lo, hi = _decimal(proposal["minimum"]), _decimal(proposal["maximum"])
    scale = 0 if col["type"] == "integer" else col["scale"]
    if not _decimal(col["min"]) <= lo <= hi <= _decimal(col["max"]) or any(not _has_scale(x, scale) for x in (lo, hi)):
        raise ValueError("Model proposal violates original bounds or precision.")
    return {"status": "review_required_not_applied", "proposal": proposal}


def run(payload, context=None):
    named, order = _validate_recipe(payload)
    proposal = _proposal(payload, named, context)
    start = perf_counter()
    records = _generate(named, order, payload["row_counts"], payload.get("seed", 41))
    generation_ms = (perf_counter() - start) * 1000
    for item in payload.get("audit_overrides", []):
        records[item["table"]][item["row"]][item["column"]] = item["value"]
    start = perf_counter()
    validation = audit(records, named)
    validation_ms = (perf_counter() - start) * 1000
    distributions = []
    for name, table in named.items():
        for col in table["columns"]:
            if col["type"] == "enum":
                observed = Counter(row[col["name"]] for row in records[name] if row[col["name"]] is not None)
                weights = col.get("weights", [1] * len(col["values"]))
                expected = dict(zip(col["values"], [w / sum(weights) for w in weights]))
                size = sum(observed.values())
                keys = set(expected) | set(observed)
                tv = sum(abs((observed[k] / size) - expected.get(k, 0)) for k in keys) / 2 if size else None
                distributions.append({"column": f"{name}.{col['name']}", "nonnull_sample_size": size, "expected": expected, "observed": dict(observed), "total_variation_distance": round(tv, 4) if tv is not None else None, "interpretation": "Descriptive sampling difference, not a population-fidelity or privacy test."})
    total, issues = sum(payload["row_counts"].values()), validation["issue_count"]
    return {
        "summary": f"{'Hold this dataset: ' + str(issues) + ' integrity issues need repair.' if issues else 'This synthetic dataset passes the declared integrity rules.'} Generated {total:,} records from original rules; this does not establish production fidelity or privacy protection.",
        "metrics": [{"label": "Synthetic records", "value": total, "unit": "records"}, {"label": "Integrity issues", "value": issues, "unit": "issues"}, {"label": "Generation time", "value": round(generation_ms, 3), "unit": "ms"}, {"label": "Validation time", "value": round(validation_ms, 3), "unit": "ms"}, {"label": "Constraint checks", "value": validation["checks"], "unit": "checks"}],
        "evidence": [f"Rule version: {payload['rules']['version']}; seed: {payload.get('seed', 41)}; parent-before-child order: {', '.join(order)}.", f"{len(payload.get('audit_overrides', []))} explicit validation probes were applied after generation.", "No customer or employer records are loaded. Distributions are invented design assumptions.", "Timings are measured locally for this run and exclude network and model latency."],
        "next_actions": ["Repair flagged records and rerun validation." if issues else "Use the deterministic fixture in integration tests; version changes to its rules.", "Have domain owners review missing cross-field constraints and intended distributions.", "Benchmark at realistic volume in isolation; evaluate privacy risk if adapting to real data."],
        "details": {"rule_version": payload["rules"]["version"], "seed": payload.get("seed", 41), "generation_order": order, "validation": validation, "distributions": distributions, "records": records, "model_rule_proposal": proposal, "measurement_scope": "Local synthetic baseline; timings vary with machine load."}}


_BROKEN = default_input()
_BROKEN["audit_overrides"] = [{"table": "orders", "row": 0, "column": "customer_id", "value": 999998}, {"table": "orders", "row": 1, "column": "amount", "value": "5000.001"}]
META = {
    "id": "synthetic_data_foundry", "title": "Synthetic Data Assurance Lab", "category": "Data architecture", "buyer": "Engineering and data executives", "question": "Can teams test realistic relationships without copying sensitive records?", "promise": "Generate reproducible relational fixtures and expose broken integrity before release.", "description": "Versioned original rules generate records; an independent auditor checks keys, domains, boundaries and precision.", "principal": "Constraint modeling, dependency scheduling, reproducibility and independent validation.", "director": "Reusable test-data capability with explicit quality gates, ownership and privacy boundaries.", "patterns": ["Constrained synthetic generation", "Structured model proposals", "Human review", "Data quality gates"], "architecture": ["Versioned original rules", "Dependency validation", "Seeded generator", "Independent constraint audit", "Distribution and timing report"], "risks": ["Synthetic distributions may miss real business behavior.", "Synthetic generation alone is not a privacy guarantee."], "limits": ["50,000 rows per run; integer primary keys and acyclic references.", "No learned generator, differential privacy, warehouse connector or production benchmark."], "flagship": True, "order": 1,
    "demo_inputs": [{"label": "Valid commerce fixture", "payload": default_input()}, {"label": "Broken relationship and precision", "payload": _BROKEN}]}
