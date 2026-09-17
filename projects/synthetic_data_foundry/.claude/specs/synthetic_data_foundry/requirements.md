# Requirements: synthetic_data_foundry

As an executive reviewer, I need an inspectable decision and its technical evidence. As an architect, I need a runnable bounded implementation with explicit failure behavior.

| ID | EARS acceptance requirement | Test evidence |
|---|---|---|
| S1 | WHEN valid original rules and a seed are supplied, THE SYSTEM SHALL generate the requested bounded records with reproducible values. | `test_seed_is_repeatable_and_changes_data; test_counts_and_dependency_order` |
| S2 | WHEN records violate keys, domains, precision or boundaries, THE SYSTEM SHALL report integrity failures independently of generation. | `test_targeted_probes_detect_fk_precision_duplicate_domain_null; test_exact_boundaries` |
| S3 | WHEN constraints are invalid or references cyclic, THE SYSTEM SHALL reject the recipe before generation. | `test_invalid_recipes_rejected; test_cycle_rejected` |
| S4 | WHEN an optional model proposes a range, THE SYSTEM SHALL validate its column, precision and bounds and keep it unapplied. | `test_model_proposal_is_validated_and_not_applied; test_model_invalid_column_bounds_precision_structure` |
| S5 | WHEN a run completes, THE SYSTEM SHALL expose separate timing measurements and descriptive distribution evidence without privacy or production-fidelity claims. | `test_default_independent_integrity; test_nullable_distribution_has_no_false_fidelity_score; test_weight_change_affects_distribution` |

Nonfunctional requirements: offline standard-library baseline; deterministic business calculations; bounded inputs; JSON-serializable outputs; no arbitrary execution or production writes. Shared provider code owns optional network access. Public examples must be original and synthetic.
