"""Independent Staff Engineer regressions; reviewer did not author the implementation."""
from copy import deepcopy
import unittest
from projects.synthetic_data_foundry.project import default_input, run

class IndependentProductReview(unittest.TestCase):
    def test_explicit_null_does_not_satisfy_required_reference_coverage(self):
        payload=default_input();payload['quality_policy']['require_reference']=True
        payload['reference_records']={'customers':None,'orders':None}
        with self.assertRaises(ValueError):run(payload)

    def test_partial_reference_cannot_claim_complete_reference_coverage(self):
        payload=default_input();records=run(payload)['details']['records']
        payload['quality_policy']['require_reference']=True;payload['reference_records']={'customers':records['customers']}
        result=run(payload)['details']['release_gate']
        self.assertEqual(result['decision'],'hold')
        self.assertFalse(next(check for check in result['checks'] if check['control']=='Reference coverage')['passed'])

    def test_reference_input_is_never_modified_by_assurance(self):
        payload=default_input();payload['reference_records']=run(payload)['details']['records'];snapshot=deepcopy(payload)
        run(payload);self.assertEqual(payload,snapshot)

    def test_mutation_probes_do_not_enter_returned_records(self):
        payload=default_input();result=run(payload)['details']
        self.assertGreater(result['mutation_campaign']['detected'],0)
        self.assertEqual(result['validation']['issue_count'],0)
        self.assertTrue(all(row['customer_id'] is not None for row in result['records']['customers']))

    def test_declared_integrity_failure_is_a_release_hold_even_with_reference(self):
        payload=default_input();payload['reference_records']=run(payload)['details']['records']
        payload['audit_overrides']=[{'table':'orders','row':0,'column':'customer_id','value':999999}]
        result=run(payload)['details'];self.assertEqual(result['release_gate']['decision'],'hold')
        self.assertEqual(result['mutation_campaign']['status'],'blocked_by_baseline')
