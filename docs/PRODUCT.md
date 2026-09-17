# Product requirements and acceptance

A reproducible test-data application that generates relational datasets, measures quality and exposure, and evaluates release controls before the data is used downstream.

## End-to-end workflow

### 1. Define a versioned recipe

Choose table counts, enum weights, exact numeric ranges, dates and declared parent relationships. The recipe is rejected before generation if a foreign-key domain cannot contain its generated parents.

### 2. Generate and independently audit

The same seed yields the same records. Optional corruption probes deliberately violate constraints after generation, so a passing generator is never used as evidence that its auditor works.

### 3. Compare utility and exposure

Inspect categorical total-variation distance, optional numeric reference comparisons, quasi-identifier group sizes and exact non-key reference overlap. Reference records must conform to declared domains.

### 4. Run the quality campaign

At most 64 individual faults test nullability, keys, domains and relationships. A corrupt baseline blocks campaign interpretation instead of treating pre-existing failures as successful mutant detection.

### 5. Review release evidence

The gate combines integrity, mutation detection, marginal utility, measured group size and required reference coverage. A model range proposal is evaluated on a separate candidate dataset and remains unapplied.

## Input contracts

| Input | Rules |
|---|---|
| `quality_policy` | minimum_group_size 1–100; maximum_distribution_distance 0–1; boolean require_reference. |
| `quasi_identifiers` | Up to eight unique declared columns per table. Default measurement uses up to two enum columns. |
| `reference_records` | Optional 1–5,000 domain-valid reference rows per declared table; never fetched from a private source. |
| `audit_overrides` | Explicit scalar cell mutations, applied only to generated baseline records. |
| `rule_request` | Optional natural-language request for a narrower independent numeric range. |

Every input is validated before it can be used to make a domain decision. Unknown or malformed evidence fails explicitly; stale evidence is retained as stale rather than silently treated as current. See [contracts](CONTRACTS.md) for the report and model boundaries.

## Results and evidence

- assurance.exposure: smallest measured group, uniqueness fraction and explicit reference overlap.
- assurance.utility: categorical distance or normalized numeric mean difference with a named baseline.
- mutation_campaign: individual injected faults, detection count, survivors and baseline status.
- release_gate: observed values, policy requirements and eligible_for_owner_review or hold.
- ai_evaluation: separate counterfactual integrity and changed-row measurements when a model proposal exists.

## Acceptance evidence

- Every supported workflow executes in local mode and returns complete bounded evidence.
- New and existing cases retain unit, boundary, AI-output and integration tests.
- Version-specific reviews become stale when their relevant source inputs change.
- Domain results are visible in the product workspace and full JSON export.
- Invalid inputs fail explicitly; generated assistance cannot override deterministic controls.
- The application and documentation accurately identify local deployment and production authority boundaries.
- Independent automated Staff Engineer review reproduces defects and retests their fixes before publication.
