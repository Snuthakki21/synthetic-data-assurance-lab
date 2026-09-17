"""Structured model assistance with deterministic evidence validation."""

from copy import deepcopy


from app.domain.schema import _decimal
from app.domain.schema import _has_scale

class RuleProposalService:
    def propose(self, payload, named, context):
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


_proposal = RuleProposalService().propose


class RuleProposalEvaluator:
    """Measure a validated model proposal on a separate seeded candidate dataset."""
    def evaluate(self, proposal, payload, baseline):
        if proposal.get('status') != 'review_required_not_applied':
            return {'status': 'no_candidate', 'applied': False, 'checks': []}
        from app.domain.schema import RecipeValidator
        from app.domain.generation import RelationalGenerator
        from app.domain.integrity import IntegrityAuditor
        candidate = deepcopy(payload)
        table_name, column_name = proposal['proposal']['column'].split('.')
        table = next(table for table in candidate['rules']['tables'] if table['name'] == table_name)
        column = next(column for column in table['columns'] if column['name'] == column_name)
        minimum, maximum = proposal['proposal']['minimum'], proposal['proposal']['maximum']
        column['min'], column['max'] = (int(minimum), int(maximum)) if column['type'] == 'integer' else (str(minimum), str(maximum))
        tables, order = RecipeValidator().validate(candidate)
        records = RelationalGenerator().generate(tables, order, candidate['row_counts'], candidate.get('seed', 41))
        audit = IntegrityAuditor().audit(records, tables)
        changed = sum(left != right for left, right in zip(baseline[table_name], records[table_name]))
        return {'status': 'counterfactual_evaluated', 'applied': False, 'column': proposal['proposal']['column'],
            'candidate_range': [column['min'], column['max']], 'candidate_integrity_issues': audit['issue_count'],
            'changed_rows_in_target_table': changed, 'candidate_rows': len(records[table_name]),
            'checks': [{'control': 'Candidate recipe valid', 'passed': True}, {'control': 'Independent candidate integrity', 'passed': audit['issue_count'] == 0}],
            'limitation': 'Counterfactual uses a separate seeded dataset. It measures declared constraints, not model reasoning quality or population fidelity.'}
