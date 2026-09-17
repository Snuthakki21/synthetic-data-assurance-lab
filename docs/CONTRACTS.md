# Data and AI contracts

## Supported input extensions

| Field | Contract |
|---|---|
| `quality_policy` | minimum_group_size 1–100; maximum_distribution_distance 0–1; boolean require_reference. |
| `quasi_identifiers` | Up to eight unique declared columns per table. Default measurement uses up to two enum columns. |
| `reference_records` | Optional 1–5,000 domain-valid reference rows per declared table; never fetched from a private source. |
| `audit_overrides` | Explicit scalar cell mutations, applied only to generated baseline records. |
| `rule_request` | Optional natural-language request for a narrower independent numeric range. |

The original domain inputs remain backward compatible. New fields are optional unless their workflow requires them. Every example is inspectable through the scenario selector and downloaded report.

## Report contract

A report contains `summary`, `metrics`, `evidence`, `next_actions` and `details`. Runtime provenance records the installed application, input digest, source digest, mode and measured execution. Arrays may be visually truncated in the UI; downloaded JSON keeps the full bounded result.

- assurance.exposure: smallest measured group, uniqueness fraction and explicit reference overlap.
- assurance.utility: categorical distance or normalized numeric mean difference with a named baseline.
- mutation_campaign: individual injected faults, detection count, survivors and baseline status.
- release_gate: observed values, policy requirements and eligible_for_owner_review or hold.
- ai_evaluation: separate counterfactual integrity and changed-row measurements when a model proposal exists.

## AI input and output authority

The optional model proposes a narrower numeric range through a closed JSON schema. An allowlist, exact-scale checks and original-bound checks reject invalid proposals. RuleProposalEvaluator generates a separate seeded candidate and runs the independent auditor again. No proposal mutates the original rules or records. This demonstrates constrained generation, deterministic guardrails, counterfactual evaluation and human acceptance as distinct responsibilities.

Provider credentials stay server-side or in the local operator's environment. The public browser application uses local algorithms. A provider is never given a database-write or release action. Every model output is untrusted until schema and domain checks pass. Coverage measurements describe fields/citations actually supplied; they are not invented accuracy, factuality or hallucination scores.

## Fixture and reference provenance

Only original synthetic scenarios are bundled. User imports may contain sensitive data and remain under the operator's control. Optional live assistance can transmit its documented domain evidence to the configured provider; review the input before enabling that mode. There is no automatic upload from the public local-mode app.

## Error behavior

Validation errors stop the affected execution with a specific message. Invalid input is not silently repaired. No incomplete domain calculation is relabeled as a completed successful report. Stale evidence is distinguishable from malformed evidence: stale records have a different revision, while malformed records violate the declared contract.
