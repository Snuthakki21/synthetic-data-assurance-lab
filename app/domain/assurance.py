"""Privacy exposure, utility comparisons and fault-injection quality campaigns.

The metrics are descriptive controls. They do not establish differential privacy,
statistical anonymity, or fidelity to any undisclosed population.
"""
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
import math
from app.domain.integrity import IntegrityAuditor, _domain_error
from app.domain.schema import _integer


@dataclass(frozen=True)
class QualityPolicy:
    minimum_group_size: int = 2
    maximum_distribution_distance: float = 0.25
    require_reference: bool = False

    @classmethod
    def from_payload(cls, value):
        if not isinstance(value, dict) or not set(value) <= {'minimum_group_size', 'maximum_distribution_distance', 'require_reference'}:
            raise ValueError('quality_policy contains unsupported fields.')
        k = value.get('minimum_group_size', 2)
        distance = value.get('maximum_distribution_distance', 0.25)
        required = value.get('require_reference', False)
        if not _integer(k) or not 1 <= k <= 100 or isinstance(distance, bool) or not isinstance(distance, (int, float)) or not math.isfinite(distance) or not 0 <= distance <= 1 or not isinstance(required, bool):
            raise ValueError('Quality policy requires group size 1–100, distance 0–1 and a boolean reference requirement.')
        return cls(k, distance, required)


@dataclass(frozen=True)
class ExposureProfile:
    table: str
    quasi_identifiers: tuple[str, ...]
    group_count: int
    smallest_group: int | None
    unique_record_fraction: float | None
    exact_reference_overlap: int | None

    def as_dict(self):
        return {'table': self.table, 'quasi_identifiers': list(self.quasi_identifiers), 'group_count': self.group_count,
                'smallest_group': self.smallest_group, 'unique_record_fraction': self.unique_record_fraction,
                'exact_reference_overlap': self.exact_reference_overlap}


class PrivacyUtilityEvaluator:
    """Compare generated rows to explicit reference rows or declared marginals."""

    def evaluate(self, payload, records, tables):
        reference = payload.get('reference_records', {})
        identifiers = payload.get('quasi_identifiers', {})
        if not isinstance(reference, dict) or not set(reference) <= set(tables) or not isinstance(identifiers, dict) or not set(identifiers) <= set(tables):
            raise ValueError('Reference records and quasi-identifiers must name declared tables.')
        profiles, utility = [], []
        for name, table in tables.items():
            fields = {col['name']: col for col in table['columns']}
            quasi = identifiers.get(name, [col['name'] for col in table['columns'] if col['type'] == 'enum'][:2])
            if not isinstance(quasi, list) or len(quasi) > 8 or len(quasi) != len(set(str(x) for x in quasi)) or any(not isinstance(col, str) or col not in fields for col in quasi):
                raise ValueError('Quasi-identifiers must be up to eight unique declared column names.')
            rows = records[name]
            ref = reference.get(name)
            if name in reference and ref is None:
                raise ValueError('An explicit reference table must contain records, not null.')
            if ref is not None:
                if not isinstance(ref, list) or not 1 <= len(ref) <= 5000:
                    raise ValueError('Reference tables require 1–5,000 records.')
                for row in ref:
                    if not isinstance(row, dict) or set(row) != set(fields) or any(_domain_error(row[key], col) for key, col in fields.items()):
                        raise ValueError('Reference rows must conform to every declared column domain.')
            groups = Counter(tuple(row[col] for col in quasi) for row in rows) if quasi else Counter()
            compare_fields = tuple(col for col in fields if col != table['primary_key'])
            ref_keys = {tuple(row[col] for col in compare_fields) for row in ref} if ref is not None else None
            overlap = sum(tuple(row[col] for col in compare_fields) in ref_keys for row in rows) if ref_keys is not None else None
            profiles.append(ExposureProfile(name, tuple(quasi), len(groups), min(groups.values()) if groups else None,
                round(sum(count == 1 for count in groups.values()) / len(rows), 6) if groups else None, overlap).as_dict())
            for key, col in fields.items():
                if col['type'] == 'enum':
                    generated = Counter(row[key] for row in rows if row[key] is not None)
                    total = sum(generated.values())
                    if ref is None:
                        weights = col.get('weights', [1] * len(col['values']))
                        baseline = {label: weight / sum(weights) for label, weight in zip(col['values'], weights)}
                    else:
                        counts = Counter(row[key] for row in ref if row[key] is not None)
                        baseline = {label: count / sum(counts.values()) for label, count in counts.items()} if counts else {}
                    tv = sum(abs(generated.get(label, 0) / total - baseline.get(label, 0)) for label in set(generated) | set(baseline)) / 2 if total and baseline else None
                    utility.append({'column': f'{name}.{key}', 'measure': 'total_variation_distance', 'value': round(tv, 6) if tv is not None else None, 'baseline': 'explicit_reference' if ref is not None else 'declared_distribution'})
                elif ref is not None and col['type'] in {'integer', 'decimal'} and key != table['primary_key'] and not col.get('references'):
                    left = [Decimal(str(row[key])) for row in rows if row[key] is not None and _domain_error(row[key], col) is None]
                    right = [Decimal(str(row[key])) for row in ref if row[key] is not None]
                    width = Decimal(str(col['max'])) - Decimal(str(col['min']))
                    delta = abs(sum(left) / len(left) - sum(right) / len(right)) if left and right else None
                    utility.append({'column': f'{name}.{key}', 'measure': 'normalized_mean_difference', 'value': float(delta / width) if delta is not None and width else 0.0 if delta == 0 else None, 'baseline': 'explicit_reference'})
        return {'exposure': profiles, 'utility': utility, 'reference_tables': sorted(reference),
                'interpretation': 'Quasi-identifier group size and overlap reveal descriptive exposure. They are not a privacy guarantee; marginal similarity does not prove joint-distribution fidelity.'}


class MutationCampaign:
    """Evaluate whether the independent auditor detects one deliberately invalid cell.

    Mutants share untouched rows with the baseline and copy only the changed row.
    One mutant is retained at a time; the campaign never stores duplicate datasets.
    """
    def run(self, records, tables):
        auditor = IntegrityAuditor()
        baseline = auditor.audit(records, tables)
        if baseline['issue_count']:
            return {'status': 'blocked_by_baseline', 'mutants': [], 'detected': 0, 'survived': 0, 'detection_rate': None}
        mutants = []
        for name, table in tables.items():
            for col in table['columns']:
                if len(mutants) >= 64:
                    break
                key, kind = col['name'], col['type']
                if not col.get('nullable', False):
                    value, fault = None, 'required_null'
                elif kind == 'enum':
                    value, fault = '__outside_declared_domain__', 'invalid_category'
                    while value in col['values']:
                        value += '_'
                elif kind in {'integer', 'decimal'}:
                    value, fault = col['max'] + 1 if kind == 'integer' else str(Decimal(str(col['max'])) + 1), 'range_overflow'
                else:
                    value, fault = 'not-a-date', 'invalid_date'
                mutants.append(self._probe(auditor, records, tables, name, key, value, fault))
                if key == table['primary_key'] and len(records[name]) > 1 and len(mutants) < 64:
                    mutants.append(self._probe(auditor, records, tables, name, key, records[name][1][key], 'duplicate_primary_key'))
                if col.get('references') and len(mutants) < 64:
                    target, target_key = col['references'].split('.')
                    parent_values = {row[target_key] for row in records[target]}
                    missing = col['max']
                    if missing not in parent_values:
                        mutants.append(self._probe(auditor, records, tables, name, key, missing, 'orphan_reference'))
        detected = sum(item['detected'] for item in mutants)
        return {'status': 'completed', 'mutants': mutants, 'detected': detected, 'survived': len(mutants) - detected,
                'detection_rate': round(detected / len(mutants), 6) if mutants else None, 'limit': 64}

    def _probe(self, auditor, records, tables, name, key, value, fault):
        mutated = dict(records)
        mutated[name] = list(records[name])
        mutated[name][0] = {**records[name][0], key: value}
        result = auditor.audit(mutated, tables)
        return {'id': f'mutation:{name}.{key}:{fault}', 'table': name, 'column': key, 'fault': fault,
                'detected': result['issue_count'] > 0, 'issue_count': result['issue_count']}


class DatasetReleaseGate:
    def evaluate(self, policy, validation, evaluation, campaign):
        distances = [item['value'] for item in evaluation['utility'] if item['value'] is not None]
        measured = [row for row in evaluation['exposure'] if row['smallest_group'] is not None]
        checks = [
            {'control': 'Declared integrity', 'passed': validation['issue_count'] == 0, 'observed': validation['issue_count'], 'requirement': 'Zero issues'},
            {'control': 'Fault detection campaign', 'passed': campaign['status'] == 'completed' and campaign['survived'] == 0, 'observed': campaign['status'], 'requirement': 'Every generated mutant detected'},
            {'control': 'Marginal utility', 'passed': bool(distances) and max(distances) <= policy.maximum_distribution_distance, 'observed': max(distances) if distances else None, 'requirement': f'Maximum distance {policy.maximum_distribution_distance}'},
            {'control': 'Quasi-identifier groups', 'passed': bool(measured) and all(row['smallest_group'] >= policy.minimum_group_size for row in measured), 'observed': min((row['smallest_group'] for row in measured), default=None), 'requirement': f'At least {policy.minimum_group_size} per measured group'},
            {'control': 'Reference coverage', 'passed': not policy.require_reference or len(evaluation['reference_tables']) == len(evaluation['exposure']), 'observed': len(evaluation['reference_tables']), 'requirement': 'Every table has explicit reference' if policy.require_reference else 'Reference optional'},
        ]
        return {'decision': 'eligible_for_owner_review' if all(item['passed'] for item in checks) else 'hold', 'checks': checks, 'authority': 'Quality recommendation only; no dataset publication or privacy certification.'}
