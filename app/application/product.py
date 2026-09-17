"""Coordinate generation, independent assurance and dataset release evidence."""
from app.domain.analysis import SyntheticDatasetService
from app.domain.assurance import QualityPolicy, PrivacyUtilityEvaluator, MutationCampaign, DatasetReleaseGate

from app.ai.assistance import RuleProposalEvaluator


class ProductApplication:
    def __init__(self):
        self.generation = SyntheticDatasetService()
        self.utility = PrivacyUtilityEvaluator()
        self.campaign = MutationCampaign()
        self.release_gate = DatasetReleaseGate()

    def execute(self, payload, context=None):
        report = self.generation.evaluate(payload, context)
        policy = QualityPolicy.from_payload(payload.get('quality_policy', {}))
        details = report['details']
        tables = {table['name']: table for table in payload['rules']['tables']}
        comparison = self.utility.evaluate(payload, details['records'], tables)
        campaign = self.campaign.run(details['records'], tables)
        gate = self.release_gate.evaluate(policy, details['validation'], comparison, campaign)
        details.update(assurance=comparison, mutation_campaign=campaign, release_gate=gate)
        report['metrics'] += [{'label': 'Faults detected', 'value': campaign['detected'], 'unit': 'mutants'}, {'label': 'Release controls passed', 'value': sum(check['passed'] for check in gate['checks']), 'unit': 'of 5'}]
        report['evidence'].append('Release decision: ' + gate['decision'] + '. Privacy exposure and marginal utility are measured separately from record integrity.')
        report['details']['ai_evaluation'] = RuleProposalEvaluator().evaluate(report['details']['model_rule_proposal'], payload, report['details']['records'])
        return report


def run(payload, context=None):
    return ProductApplication().execute(payload, context)
