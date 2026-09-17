# Independent automated Staff Engineer review — expanded application

Review date: 2026-09-17. The reviewer is a separate automated agent that did not author this product expansion. This is an automated engineering review, not an external human audit or a production certification.

## Scope and method

Reviewed the current product diff against the published baseline, expanded product requirements and contracts, all product-specific app/domain, app/application and app/ai modules, compatibility adapter, domain UI template and domain tests. Read actual behavior before forming findings. Independently exercised adverse inputs and added tests/test_product_review.py. The product author made implementation fixes; the reviewer separately retested them.

Shared platform persistence/HTTP, packaging, hosted CI, browser visual verification and live provider quality are outside this domain review. Their checks require separate current evidence. Historical review files do not substitute for this review.

## Verdict

**Pass for the documented product scope after the corrections below. No unresolved finding was reproduced in this review.** This verdict is limited to the listed source hashes and executed checks; it does not imply a defect-free or production-certified system.

## Architecture and requirement assessment

Recipe validation, relational generation, independent integrity audit, privacy/utility metrics, mutation campaign, release control and AI counterfactual evaluation are separated into substantive services. The measured release controls add executable behavior; the adapter does not contain a duplicate engine.

New computed controls appear in the product-specific template and in the full report. The templates retain escaped rendering of untrusted data; rebuilt executed examples pass the frontend suite. Current documentation describes implemented algorithms and bounded operator authority without promising real financial/infrastructure writes or unmeasured model accuracy.

## Findings and resolution

### SYN-1 — P1: Explicit null reference tables satisfied the required-reference control.

Reproduction: A default request with require_reference=true and both table references set to null returned eligible_for_owner_review.

Resolution and retest: Explicit null references now fail validation. The independent regression requires rejection; partial reference coverage remains a hold.

Status: closed by implementation change and independent verification.

### SYN-2 — P2: The row-count control advertised zero although the backend requires at least one row.

Reproduction: The rendered number input had min=0.

Resolution and retest: The control now advertises min=1 and the supported 25,000 per-table ceiling.

Status: closed by implementation change and independent verification.

## Executed verification

- Full Python suite: 102 tests discovered, zero failures, two explicit absent-project skips. This run included the independent review cases after the behavioral corrections.
- Final domain-product rerun after import/format/document cleanup: 22 tests passed, zero skips or failures.
- Static build: one standalone product built successfully with all published scenarios.
- Frontend suite on the rebuilt catalog: 31 tests, 25 passed, six explicit absent-project skips, zero failures.
- Independent review regressions: 5 tests passed.
- README and maintained docs relative-link validation found no missing targets.

Commands:

```sh
python3 -m unittest discover -s tests
python3 -m unittest discover -s tests -p 'test_product*.py'
python3 -m portfolio build --output dist
node --test --test-timeout=20000 tests/frontend.test.mjs
```

## Source snapshot

[Machine-readable source snapshot](STAFF_REVIEW_V2_SOURCE.json) and the SHA-256 digests below identify the reviewed product implementation. Future edits to these files require renewed review of the changed behavior.

| File | SHA-256 |
|---|---|
| `app/ai/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `app/ai/assistance.py` | `4ccf52d8a5d6aaa2dbbba0cd466ac8c7a95da06ee3d4beb9dc68d5d428805a19` |
| `app/application/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `app/application/product.py` | `843518ca5ca4637b30687f5ac414905cc8eea19b70a5412e674b83090bb47714` |
| `app/domain/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `app/domain/analysis.py` | `d29c952ab052636388b17fb84deb9ef3c6d3d49e6cb86a705186fb788b76a9c7` |
| `app/domain/assurance.py` | `201d98298dc726e2289864881e3d46cbdbfd57d864638960200f77c215621759` |
| `app/domain/generation.py` | `2bc80743841e5037ce7832b2923a2d7e0e6f541d87c1c895ae2a418ffe86de36` |
| `app/domain/integrity.py` | `27de4102993093bd0278ea0031f3cf0eea91af835fb3184915c2fdf48ff65370` |
| `app/domain/schema.py` | `e713954819fdbfed7d10ada4ccd177f152e035bf4acaa9614d954a689b88dc73` |
| `docs/PRODUCT.md` | `50f0d3a6790782d0e7e354528b578eed75265c989ccb8c89af262e7e054b0d0f` |
| `projects/synthetic_data_foundry/project.py` | `b3def9fb894e5d2fbfdf22964a52f2af946f08b7135881e8a296c2fcb3d8741e` |
| `tests/test_product_review.py` | `ab821695ac78f6cb13fcaa8718c77f080dc6de7f61b7480d1b28953da4a93c2e` |
| `web/templates/synthetic_data_foundry.js` | `ecce177a90215a8b7125909d0286dd355ca04135b3095f311743933d92a642f6` |
