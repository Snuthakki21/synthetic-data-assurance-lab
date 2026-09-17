"""Behavioral tests for generation quality, privacy exposure and fault detection."""
import unittest
from copy import deepcopy
from app.application.product import ProductApplication
from app.domain.assurance import QualityPolicy, PrivacyUtilityEvaluator, MutationCampaign, DatasetReleaseGate
from projects.synthetic_data_foundry.project import default_input, run, META


class AssuranceTests(unittest.TestCase):
    def test_default_release_evidence_has_detected_mutants(self):
        d = ProductApplication().execute(default_input())['details']
        self.assertEqual(d['release_gate']['decision'], 'eligible_for_owner_review')
        self.assertGreater(len(d['mutation_campaign']['mutants']), 8)
        self.assertEqual(d['mutation_campaign']['survived'], 0)
        self.assertIn('orphan_reference', {m['fault'] for m in d['mutation_campaign']['mutants']})

    def test_unique_identifier_exposure_holds_dataset(self):
        p = default_input(); p['quasi_identifiers'] = {'customers': ['customer_id']}
        d = run(p)['details']; row = d['assurance']['exposure'][0]
        self.assertEqual(row['smallest_group'], 1)
        self.assertEqual(row['unique_record_fraction'], 1)
        self.assertEqual(d['release_gate']['decision'], 'hold')

    def test_explicit_reference_is_compared_and_not_claimed_private(self):
        p = default_input(); p['reference_records'] = run(p)['details']['records']
        p['quality_policy']['require_reference'] = True
        d = run(p)['details']
        self.assertEqual(d['assurance']['reference_tables'], ['customers', 'orders'])
        self.assertTrue(all(row['value'] == 0 for row in d['assurance']['utility']))
        self.assertEqual(d['assurance']['exposure'][1]['exact_reference_overlap'], 200)

    def test_reference_requirement_requires_every_table(self):
        p = default_input(); p['quality_policy']['require_reference'] = True
        self.assertEqual(run(p)['details']['release_gate']['decision'], 'hold')

    def test_mutation_does_not_modify_original_dataset(self):
        p = default_input(); records = run(p)['details']['records']; snapshot = deepcopy(records)
        MutationCampaign().run(records, {t['name']: t for t in p['rules']['tables']})
        self.assertEqual(records, snapshot)

    def test_corrupt_baseline_blocks_mutation_interpretation(self):
        p = default_input(); p['audit_overrides'] = [{'table': 'orders', 'row': 0, 'column': 'amount', 'value': '-1'}]
        d = run(p)['details']
        self.assertEqual(d['mutation_campaign']['status'], 'blocked_by_baseline')
        self.assertIsNone(d['mutation_campaign']['detection_rate'])

    def test_nullable_types_receive_type_specific_faults(self):
        p = default_input()
        for table in p['rules']['tables']:
            for col in table['columns']:
                if col['name'] != table['primary_key']:
                    col['nullable'] = True
        d = run(p)['details']
        faults = {m['fault'] for m in d['mutation_campaign']['mutants']}
        self.assertTrue({'invalid_category', 'invalid_date', 'range_overflow'} <= faults)
        self.assertEqual(d['mutation_campaign']['survived'], 0)

    def test_null_only_enum_has_unavailable_distribution(self):
        p = default_input(); col = p['rules']['tables'][0]['columns'][1]
        col.update(nullable=True, null_rate=1)
        d = run(p)['details']
        self.assertIsNone(next(x for x in d['assurance']['utility'] if x['column']=='customers.segment')['value'])

    def test_quality_policy_rejects_invalid_fields_and_types(self):
        for policy in [None, {'unknown': 1}, {'minimum_group_size': True}, {'minimum_group_size': 0}, {'minimum_group_size': 101}, {'maximum_distribution_distance': False}, {'maximum_distribution_distance': float('nan')}, {'maximum_distribution_distance': -0.1}, {'require_reference': 'yes'}]:
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                QualityPolicy.from_payload(policy)

    def test_reference_contract_rejects_malformed_rows(self):
        for reference in [[], {'absent': []}, {'customers': []}, {'customers': [None]}, {'customers': [{'customer_id': 1001}]}, {'customers': [{'customer_id': False, 'segment': 'consumer', 'joined_on': '2025-01-01'}]}]:
            p = default_input(); p['reference_records'] = reference
            with self.subTest(reference=reference), self.assertRaises(ValueError): run(p)

    def test_quasi_identifier_contract_rejects_unknown_and_duplicates(self):
        for identifiers in [[], {'missing': []}, {'customers': ['unknown']}, {'customers': ['segment', 'segment']}, {'customers': [1]}, {'customers': 'segment'}]:
            p = default_input(); p['quasi_identifiers'] = identifiers
            with self.subTest(identifiers=identifiers), self.assertRaises(ValueError): run(p)

    def test_zero_numeric_width_and_null_references(self):
        p = default_input(); p['rules']['tables'][1]['columns'][2].update(min='1.00',max='1.00')
        p['reference_records'] = run(p)['details']['records']
        d = run(p)['details']
        self.assertEqual(next(x['value'] for x in d['assurance']['utility'] if x['measure']=='normalized_mean_difference'), 0)

    def test_high_distance_blocks_release(self):
        p = default_input(); p['quality_policy']['maximum_distribution_distance'] = 0
        self.assertEqual(run(p)['details']['release_gate']['decision'], 'hold')

    def test_empty_quasi_identifier_measurement_is_explicit(self):
        p = default_input(); p['quasi_identifiers'] = {'customers': [], 'orders': []}
        d = run(p)['details']
        self.assertTrue(all(x['smallest_group'] is None for x in d['assurance']['exposure']))
        self.assertEqual(d['release_gate']['decision'], 'hold')

    def test_all_published_scenarios_execute(self):
        for scenario in META['demo_inputs']:
            with self.subTest(scenario=scenario['label']): self.assertIn('release_gate', run(scenario['payload'])['details'])

class ModelCounterfactualTests(unittest.TestCase):
    def test_model_proposal_is_evaluated_without_applying_it(self):
        class Model:
            def generate_json(self, **kwargs):
                return {'column':'orders.amount','minimum':10,'maximum':20,'rationale':'Concentrate the original boundary fixture.'}
        p=default_input();d=run(p,Model())['details']
        evaluation=d['ai_evaluation']
        self.assertEqual(evaluation['status'],'counterfactual_evaluated')
        self.assertEqual(evaluation['candidate_integrity_issues'],0)
        self.assertFalse(evaluation['applied'])
        self.assertGreater(evaluation['changed_rows_in_target_table'],0)
        self.assertTrue(any(float(row['amount'])>20 for row in d['records']['orders']))

    def test_missing_model_output_is_not_scored(self):
        self.assertEqual(run(default_input())['details']['ai_evaluation']['status'],'no_candidate')
