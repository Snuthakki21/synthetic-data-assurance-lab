"""Integrity domain policies and services."""


from datetime import date


from app.domain.schema import _decimal
from app.domain.schema import _has_scale
from app.domain.schema import _integer

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


class IntegrityAuditor:
    def audit(self, records, tables):
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


audit = IntegrityAuditor().audit
