"""Compatibility entry point and original example scenarios."""

from copy import deepcopy


from app.domain.schema import _decimal
from app.domain.integrity import _domain_error
from app.domain.generation import _generate
from app.domain.schema import _has_scale
from app.domain.schema import _integer
from app.ai.assistance import _proposal
from app.domain.schema import _validate_recipe
from app.domain.integrity import audit
from app.application.product import ProductApplication, run

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


DEFAULT['quality_policy'] = {'minimum_group_size': 2, 'maximum_distribution_distance': 0.25, 'require_reference': False}
DEFAULT['quasi_identifiers'] = {}
DEFAULT['reference_records'] = {}


def default_input():
    return deepcopy(DEFAULT)


_BROKEN = default_input()


_BROKEN["audit_overrides"] = [{"table": "orders", "row": 0, "column": "customer_id", "value": 999998}, {"table": "orders", "row": 1, "column": "amount", "value": "5000.001"}]


META = {
    "id": "synthetic_data_foundry", "title": "Synthetic Data Assurance Lab", "category": "Data architecture", "buyer": "Engineering and data executives", "question": "Can teams test realistic relationships without copying sensitive records?", "promise": "Generate reproducible relational fixtures and expose broken integrity before release.", "description": "Versioned original rules generate records; an independent auditor checks keys, domains, boundaries and precision.", "principal": "Constraint modeling, dependency scheduling, reproducibility and independent validation.", "director": "Reusable test-data capability with explicit quality gates, ownership and privacy boundaries.", "patterns": ["Constrained synthetic generation", "Structured model proposals", "Human review", "Data quality gates"], "architecture": ["Versioned original rules", "Dependency validation", "Seeded generator", "Independent constraint audit", "Distribution and timing report"], "risks": ["Synthetic distributions may miss real business behavior.", "Synthetic generation alone is not a privacy guarantee."], "limits": ["50,000 rows per run; integer primary keys and acyclic references.", "No learned generator, differential privacy, warehouse connector or production benchmark."], "flagship": True, "order": 1,
    "demo_inputs": [{"label": "Valid commerce fixture", "payload": default_input()}, {"label": "Broken relationship and precision", "payload": _BROKEN}]}


_EXPOSURE = default_input()
_EXPOSURE['quasi_identifiers']['customers'] = ['customer_id']
_REFERENCE = default_input()
_REFERENCE['reference_records'] = run(_REFERENCE)['details']['records']
_REFERENCE['quality_policy']['require_reference'] = True
META['demo_inputs'].extend([{'label': 'Unique identifier exposure hold', 'payload': _EXPOSURE}, {'label': 'Explicit reference comparison', 'payload': _REFERENCE}])
