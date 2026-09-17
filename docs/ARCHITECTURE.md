# Synthetic Data Assurance Lab architecture

## Domain boundary

A reproducible test-data application that generates relational datasets, measures quality and exposure, and evaluates release controls before the data is used downstream.

QualityPolicy and ExposureProfile represent validated policy and measured exposure. Rules and records stay separate from model proposals.

## Responsibilities

| Module | Service or value object | Responsibility |
|---|---|---|
| `schema.py` | `RecipeValidator` | Validates versioned tables, exact bounds, nullable policies and acyclic parent dependencies. |
| `generation.py` | `RelationalGenerator` | Produces reproducible parent-before-child datasets with seeded sampling. |
| `integrity.py` | `IntegrityAuditor` | Independently checks types, domains, decimal precision, uniqueness and foreign keys. |
| `assurance.py` | `PrivacyUtilityEvaluator / MutationCampaign / DatasetReleaseGate` | Computes exposure and utility, injects bounded faults and combines explicit release controls. |
| `analysis.py` | `SyntheticDatasetService` | Assembles generation, validation and distribution evidence. |

The application layer coordinates services through explicit inputs and returns a serializable report. Domain code does not open sockets, modify source systems or read a shared database. Model assistance is passed as a context with a constrained `generate_json` capability; no domain service obtains credentials directly.

## Runtime boundary

The shared platform stores versioned scenarios and completed or failed execution records through a SQLite repository in native mode. The browser runs the same domain package and retains browser-local scenario/history records. Neither persistence mode grants domain authority to approve production changes, write customer systems or bypass input validation.

## Dependency direction

`projects` adapter → `app.application` → `app.domain` and `app.ai`. Domain modules depend on the standard library and sibling domain value policies. Platform repository models are separate from product domain entities. Existing imports remain compatibility aliases to their actual service implementations so integrations can migrate without maintaining a duplicate algorithm.

## Architecture decisions

1. Deterministic controls remain authoritative. Generative assistance can propose or explain, and must pass bounded schema and domain checks.
2. Exact numeric representations are preserved at external boundaries; JSON payloads never imply hidden binary-float accounting precision.
3. Review evidence names an exact revision wherever a changed input could invalidate the decision. A stale record remains visible rather than being silently updated.
4. Limits are explicit and fail closed. Unsupported grammar, malformed records and unsupported money rules do not receive guessed interpretations.
5. Product-specific algorithms are isolated from transport and persistence so unit tests can exercise meaningful behavior without a live provider or server.

## Known tradeoffs

Original invented rules do not reproduce a private population. Marginal similarity does not establish joint-distribution fidelity, causal validity, anonymity or differential privacy. Generation is bounded to 50,000 rows, 12 tables and 32 columns per table; mutation campaigns retain one changed dataset view at a time. No external target-database writer, warehouse connector or publication service is present. Native workspace SQLite stores scenario, execution and review records; it does not write generated datasets into operational target systems.

## Failure containment

A failed integrity baseline prevents meaningful mutation scoring. Fix the named cell or recipe and rerun. If utility fails, inspect the named baseline and sample size before changing the threshold. If exposure fails, reconsider quasi-identifiers and intended use rather than relabeling the dataset private.
