# Operator workflows

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

## Scenario management

Keep baseline and candidate scenarios separately named. Save a revision before execution when you need a reproducible comparison. Compare completed runs using their input and report evidence; a changed metric is a reason to inspect its source, not proof of improvement. Retain the exported report when a decision must be shared outside the local workspace.

## AI-assisted workflow

The optional model proposes a narrower numeric range through a closed JSON schema. An allowlist, exact-scale checks and original-bound checks reject invalid proposals. RuleProposalEvaluator generates a separate seeded candidate and runs the independent auditor again. No proposal mutates the original rules or records. This demonstrates constrained generation, deterministic guardrails, counterfactual evaluation and human acceptance as distinct responsibilities.

## Review handoff

Give the reviewer the exact input, complete downloaded report, revision identifiers, control failures and any model draft. Explain which evidence is computed and which is an operator attestation. A reviewer should be able to reproduce the result in local mode without a secret credential.
