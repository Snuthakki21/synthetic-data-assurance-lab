# Product runbook

## Start and verify

Use the commands in the README. Execute the default case, a held case and the relevant review/evidence case after changing domain rules or upgrading a dependency. Verify that the displayed decision, exception evidence and downloaded report agree. Run unit/integration tests before publishing a new application build.

## Investigate a failed execution

A failed integrity baseline prevents meaningful mutation scoring. Fix the named cell or recipe and rerun. If utility fails, inspect the named baseline and sample size before changing the threshold. If exposure fails, reconsider quasi-identifiers and intended use rather than relabeling the dataset private.

## Preserve evidence

Keep source input revisions separate from review annotations. Do not edit an exported report and present it as a generated result. Re-execute a new revision after changes, then collect new review evidence where the application marks an old decision stale. The workspace audit trail is operational history for this local application, not a legally authenticated signature system.

## Model availability

Local mode remains available without a provider. Provider outages, timeouts and schema failures must be reported as errors or unavailable assistance; they must not be replaced with fabricated model output. A successful schema check still requires the product-specific checks described in CONTRACTS.md.

## Capacity and operational boundary

Original invented rules do not reproduce a private population. Marginal similarity does not establish joint-distribution fidelity, causal validity, anonymity or differential privacy. Generation is bounded to 50,000 rows, 12 tables and 32 columns per table; mutation campaigns retain one changed dataset view at a time. No external target-database writer, warehouse connector or publication service is present. Native workspace SQLite stores scenario, execution and review records; it does not write generated datasets into operational target systems.

Use bounded original fixtures for public demonstrations. Establish workload-specific performance and recovery budgets before importing larger operational extracts. Do not expose a local single-operator server directly as a shared production service.
