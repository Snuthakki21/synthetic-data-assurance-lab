"""Application use case: coordinate validated domain services into a report."""
from collections import Counter


from time import perf_counter

from app.domain.generation import _generate
from app.ai.assistance import _proposal
from app.domain.schema import _validate_recipe
from app.domain.integrity import audit

class SyntheticDatasetService:
    def evaluate(self, payload, context=None):
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
