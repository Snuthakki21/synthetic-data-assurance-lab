# Engineering review: synthetic_data_foundry

Scope: this project's implementation, original fixtures, README and unit tests. Review performed against the local code and executable scenarios before public export.

## Actual plugin contributions

- **Ponytail ultra:** retained Python standard-library primitives and the existing portfolio contract. Removed any need for a framework, database or separate agent orchestrator. Bounded in-memory processing or parser scope carries an explicit `ponytail:` comment naming the upgrade boundary. Full requested validation and tests were preserved; the user's functional scope was not reduced.
- **Spec Driven:** captured EARS requirements, design boundaries and wired/verified tasks in `.claude/specs/synthetic_data_foundry/`. Each acceptance condition maps to named tests below. The plugin's autonomous commit scripts were not run because repository export and personal-account commits belong to the shared publishing workflow.
- **Archcore review:** applied the bidirectional code/document check to the supplied project scope. Supported syntax, uncertainty claims, optional model behavior and evidence fields were compared with `project.py` and tests. No Archcore MCP tools were available in this agent's callable tool inventory, so no managed knowledge-base initialization or formal remote audit is claimed. Local scope was explicit and needed no inferred branch boundary.
- **Codebase Recon:** probed the workspace with `git rev-parse --show-toplevel`; it was not yet a Git repository. Historical hotspots, contributor rankings, bus factor and momentum were therefore unavailable, not fabricated. Static risk inspection focused on parser/validation boundaries and model-result validation. Rerun historical analysis after substantive repository history exists.

## Acceptance coverage

| ID | Requirement | Executable checks |
|---|---|---|
| S1 | WHEN valid original rules and a seed are supplied, THE SYSTEM SHALL generate the requested bounded records with reproducible values. | `test_seed_is_repeatable_and_changes_data; test_counts_and_dependency_order` |
| S2 | WHEN records violate keys, domains, precision or boundaries, THE SYSTEM SHALL report integrity failures independently of generation. | `test_targeted_probes_detect_fk_precision_duplicate_domain_null; test_exact_boundaries` |
| S3 | WHEN constraints are invalid or references cyclic, THE SYSTEM SHALL reject the recipe before generation. | `test_invalid_recipes_rejected; test_cycle_rejected` |
| S4 | WHEN an optional model proposes a range, THE SYSTEM SHALL validate its column, precision and bounds and keep it unapplied. | `test_model_proposal_is_validated_and_not_applied; test_model_invalid_column_bounds_precision_structure` |
| S5 | WHEN a run completes, THE SYSTEM SHALL expose separate timing measurements and descriptive distribution evidence without privacy or production-fidelity claims. | `test_default_independent_integrity; test_nullable_distribution_has_no_false_fidelity_score; test_weight_change_affects_distribution` |

Run `python -m unittest discover -s tests -p 'test_synthetic_data_foundry.py' -v` from the repository root. At this review, 17 test methods passed with additional parameterized subcases. Measured module-only line and branch coverage, source hashes and test hashes are recorded in [coverage-summary.json](coverage-summary.json). Shared integration and independent review are tracked separately. Coverage measures execution, not proof of semantic correctness.

## Architecture verdict

**ok:** deterministic acceptance decisions, bounded unsupported-input rejection, original fixtures, review-only model assistance and documented limits match the inspected implementation. **ok:** README distinguishes local fixture evidence from production outcomes. Model output tests use controlled injected responses; a passing test is not evidence of a live provider call.

Residual work for production is stated in README. The current implementation does not connect employer systems, deploy a service, certify compliance or perform production writes. Readiness here means the declared local reference application and its evidence are runnable.

An independent automated reviewer identified precision loss when a nonzero fractional tail exceeded Decimal context precision. The author replaced arithmetic scale checks with coefficient/exponent digit checks, added rejection and exact-trailing-zero regressions, and refreshed the measured source/test hashes. Independent retest is recorded separately.
