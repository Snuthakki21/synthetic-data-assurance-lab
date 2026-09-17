"""Independent reviewer regressions; this reviewer did not author the application."""
import unittest
from copy import deepcopy
from projects.synthetic_data_foundry.project import default_input,run

class IndependentSyntheticReview(unittest.TestCase):
    def test_long_nonzero_subscale_value_is_rejected(self):
        p=default_input();p['rules']['tables'][1]['columns'][2]['min']='0.100000000000000000000000000001'
        with self.assertRaises(ValueError):run(p)
        p['rules']['tables'][1]['columns'][2]['min']='0.100000000000000000000000000000'
        self.assertEqual(run(p)['details']['validation']['issue_count'],0)

    def test_audit_checks_override_precision_not_only_recipe(self):
        p=default_input();p['audit_overrides']=[dict(table='orders',row=0,column='amount',value='0.100000000000000000000000000001')]
        r=run(p)['details']['validation']
        self.assertGreater(r['issue_count'],0)

    def test_multiple_defects_are_visible_and_input_preserved(self):
        p=default_input();p['audit_overrides']=[dict(table='orders',row=0,column='customer_id',value=999998),dict(table='orders',row=1,column='status',value=True)]
        before=deepcopy(p);r=run(p)
        self.assertIn('Hold',r['summary']);self.assertGreaterEqual(r['details']['validation']['issue_count'],2)
        self.assertEqual(p,before)

    def test_seed_changes_records_but_preserves_constraints(self):
        p=default_input();first=run(p)['details'];p['seed']+=1;second=run(p)['details']
        self.assertNotEqual(first['records'],second['records'])
        self.assertEqual(second['validation']['issue_count'],0)
