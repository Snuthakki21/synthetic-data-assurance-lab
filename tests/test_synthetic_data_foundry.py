import unittest
from copy import deepcopy
from projects.synthetic_data_foundry.project import default_input, run, META


class Model:
    def __init__(self, result):
        self.result = result
    def generate_json(self, **kwargs):
        return self.result


class SyntheticDataTests(unittest.TestCase):
    def test_default_independent_integrity(self):
        result = run(default_input())
        self.assertEqual(result['details']['validation']['issue_count'], 0)
        rows = result['details']['records']
        parents = {row['customer_id'] for row in rows['customers']}
        self.assertEqual(len(parents), 40)
        self.assertTrue(all(row['customer_id'] in parents for row in rows['orders']))
        self.assertTrue(all(0 <= float(row['amount']) <= 5000 for row in rows['orders']))
        self.assertEqual(result['metrics'][0]['value'], 240)

    def test_seed_is_repeatable_and_changes_data(self):
        first = default_input()
        self.assertEqual(run(first)['details']['records'], run(first)['details']['records'])
        second = deepcopy(first)
        second['seed'] += 1
        self.assertNotEqual(run(first)['details']['records'], run(second)['details']['records'])

    def test_counts_and_dependency_order(self):
        payload = default_input()
        payload['rules']['tables'].reverse()
        payload['row_counts'] = {'customers': 2, 'orders': 3}
        result = run(payload)['details']
        self.assertEqual(result['generation_order'], ['customers', 'orders'])
        self.assertEqual(len(result['records']['orders']), 3)

    def test_targeted_probes_detect_fk_precision_duplicate_domain_null(self):
        payload = default_input()
        payload['audit_overrides'] = [
            {'table': 'orders', 'row': 0, 'column': 'customer_id', 'value': 999998},
            {'table': 'orders', 'row': 1, 'column': 'amount', 'value': '1.001'},
            {'table': 'orders', 'row': 2, 'column': 'order_id', 'value': 1},
            {'table': 'orders', 'row': 3, 'column': 'status', 'value': 'invented'},
            {'table': 'orders', 'row': 4, 'column': 'status', 'value': None}]
        validation = run(payload)['details']['validation']
        self.assertEqual(validation['issue_count'], 5)
        self.assertIn('foreign key has no parent', {i['reason'] for i in validation['issues']})

    def test_exact_boundaries(self):
        payload = default_input()
        col = payload['rules']['tables'][1]['columns'][2]
        col['min'] = col['max'] = '1.23'
        result = run(payload)['details']
        self.assertEqual({row['amount'] for row in result['records']['orders']}, {'1.23'})
        self.assertEqual(result['validation']['issue_count'], 0)

    def test_nullable_distribution_has_no_false_fidelity_score(self):
        payload = default_input()
        col = payload['rules']['tables'][0]['columns'][1]
        col.update(nullable=True, null_rate=1)
        result = run(payload)['details']
        self.assertEqual(result['validation']['issue_count'], 0)
        distribution = result['distributions'][0]
        self.assertEqual(distribution['nonnull_sample_size'], 0)
        self.assertIsNone(distribution['total_variation_distance'])

    def test_weight_change_affects_distribution(self):
        payload = default_input()
        col = payload['rules']['tables'][1]['columns'][3]
        col['weights'] = [0.000001, 1, 0.000001]
        observed = run(payload)['details']['distributions'][1]['observed']
        self.assertEqual(observed.get('paid'), 200)

    def test_invalid_recipes_rejected(self):
        mutations = [
            lambda p: p.update(seed=True),
            lambda p: p['row_counts'].update(orders=0),
            lambda p: p['row_counts'].update(extra=1),
            lambda p: p['rules']['tables'][0]['columns'][0].update(max=1001),
            lambda p: p['rules']['tables'][1]['columns'][2].update(scale=8),
            lambda p: p['rules']['tables'][1]['columns'][2].update(min='NaN'),
            lambda p: p['rules']['tables'][1]['columns'][2].update(max='0.001'),
            lambda p: p['rules']['tables'][0]['columns'][2].update(min='not-a-date'),
            lambda p: p['rules']['tables'][0]['columns'][2].update(min='2026-01-01'),
            lambda p: p['rules']['tables'][1]['columns'][3].update(weights=[1,-1,1]),
            lambda p: p['rules']['tables'][1]['columns'][3].update(type=[]),
            lambda p: p['rules']['tables'][1]['columns'][3].update(null_rate=0.2),
            lambda p: p['rules']['tables'][1]['columns'][1].update(references='absent.id'),
            lambda p: p['rules']['tables'][1]['columns'][1].update(min=1100),
            lambda p: p.update(audit_overrides=[{'table': [], 'row': 0, 'column': 'x', 'value': 1}])]
        for change in mutations:
            with self.subTest(change=change):
                payload=default_input(); change(payload)
                with self.assertRaises(ValueError): run(payload)

    def test_cycle_rejected(self):
        payload=default_input()
        payload['rules']['tables'][0]['columns'].append({'name':'order_id','type':'integer','min':1,'max':999999,'references':'orders.order_id'})
        with self.assertRaisesRegex(ValueError, 'Cyclic'): run(payload)

    def test_model_proposal_is_validated_and_not_applied(self):
        payload=default_input(); payload['rule_request']='Constrain order amounts to 10 through 20.'
        result=run(payload, Model({'column':'orders.amount','minimum':10,'maximum':20,'rationale':'A boundary scenario.'}))['details']
        self.assertEqual(result['model_rule_proposal']['status'], 'review_required_not_applied')
        self.assertTrue(any(float(row['amount'])>20 for row in result['records']['orders']))
        self.assertEqual(run(payload, Model(None))['details']['model_rule_proposal']['status'], 'local_mode_no_model_proposal')

    def test_model_invalid_column_bounds_precision_structure(self):
        payload=default_input(); payload['rule_request']='Suggest constraints'
        for proposal in [ {'column':'other.amount','minimum':1,'maximum':2,'rationale':'x'}, {'column':'orders.amount','minimum':2,'maximum':1,'rationale':'x'}, {'column':'orders.amount','minimum':-1,'maximum':2,'rationale':'x'}, {'column':'orders.amount','minimum':1.001,'maximum':2,'rationale':'x'}, {'column':[],'minimum':1,'maximum':2,'rationale':'x'}, {}]:
            with self.subTest(proposal=proposal), self.assertRaises(ValueError): run(payload,Model(proposal))

    def test_every_demo_runs(self):
        for fixture in META['demo_inputs']:
            with self.subTest(label=fixture['label']): self.assertIn('summary',run(fixture['payload']))


class SyntheticBoundaryTests(unittest.TestCase):
    def test_invalid_schema_shapes_and_domains(self):
        for value in [None, [], {}, {'seed':1,'rules':{'version':'x','tables':[]},'row_counts':{}}]:
            with self.subTest(value=value),self.assertRaises(ValueError):run(value)
        edits=[lambda p:p['rules']['tables'].__setitem__(0,None),lambda p:p['rules']['tables'][0].update(name='BAD NAME'),lambda p:p['rules']['tables'][0].update(columns=[]),lambda p:p['rules']['tables'][0]['columns'].__setitem__(0,None),lambda p:p['rules']['tables'][0]['columns'][1].update(name='customer_id'),lambda p:p['rules']['tables'][0]['columns'][0].update(min=False),lambda p:p['rules']['tables'][0]['columns'][1].update(values=['x','x']),lambda p:p['rules']['tables'][1]['columns'][1].update(references='bad'),lambda p:p.update(audit_overrides=[{}]*101),lambda p:p.update(audit_overrides=[{'table':'orders','row':0,'column':'amount','value':float('nan')}]),lambda p:p.update(rule_request=42),lambda p:p['rules']['tables'][1]['columns'][2].update(min='invalid')]
        for edit in edits:
            payload=default_input();edit(payload)
            with self.subTest(edit=edit),self.assertRaises(ValueError):run(payload)

    def test_additional_numeric_types_and_invalid_audit_values(self):
        payload=default_input();payload['rules']['tables'][0]['columns'].append({'name':'age','type':'integer','min':0,'max':99})
        payload['audit_overrides']=[{'table':'orders','row':0,'column':'amount','value':True},{'table':'orders','row':1,'column':'amount','value':'bad'},{'table':'customers','row':0,'column':'joined_on','value':'not-date'}]
        result=run(payload)['details']
        self.assertEqual(result['validation']['issue_count'],3)
        self.assertTrue(all(0<=r['age']<=99 for r in result['records']['customers']))

    def test_proposal_requires_a_numeric_target(self):
        payload=default_input();payload['rules']['tables'][1]['columns']=[c for c in payload['rules']['tables'][1]['columns'] if c['name']!='amount']
        with self.assertRaisesRegex(ValueError,'independent numeric'):run(payload,Model(None))


class SyntheticIndependentFindingRegressions(unittest.TestCase):
    def test_nonzero_precision_beyond_decimal_context_is_rejected(self):
        payload=default_input();payload['rules']['tables'][1]['columns'][2]['min']='0.100000000000000000000000000001'
        with self.assertRaises(ValueError):run(payload)
        payload=default_input();payload['audit_overrides']=[{'table':'orders','row':0,'column':'amount','value':'0.100000000000000000000000000001'}]
        self.assertEqual(run(payload)['details']['validation']['issue_count'],1)

    def test_exact_trailing_zeros_remain_valid(self):
        payload=default_input();column=payload['rules']['tables'][1]['columns'][2];column['min']=column['max']='0.100000000000000000000000000000'
        result=run(payload)['details']
        self.assertEqual({r['amount'] for r in result['records']['orders']},{'0.10'})
        self.assertEqual(result['validation']['issue_count'],0)

if __name__=='__main__': unittest.main()
