# Version 2 validation

Verified 2026-09-17. This report records executed checks, separate from the domain and shared-platform reviewer verdicts.

| Check | Observed result |
|---|---|
| Python domain, runtime, API, storage and independent regression suites | 142 passed; 2 absent-project cases skipped |
| JavaScript domain presentation, interaction state and workspace suites | 48 passed; 6 absent-project cases skipped |
| Measured Python statement + branch coverage | **98.06%** across `app`, `portfolio` and `projects` |
| Static build with executed scenarios | 4 scenarios, one product |
| Actual browser execution | Fresh Python-worker result and retained execution history observed |
| Mobile layout | Workspace and scenario library fit the 390px test viewport without page overflow |
| Installed wheel | CLI/list/default run/explicit run/build passed outside source checkout; fixtures/runtime licenses and checksums verified |
| Independent automated review | Domain and shared-platform findings corrected and independently retested |

The shared test harness skips cases for products absent from this standalone distribution; skips are not counted as passes. Measurements include existing failure-path tests and newly authored independent regression tests. Coverage describes executed branches, not a guarantee of correctness on every possible input.

## Reproduce

```sh
python -m pip install -r requirements-dev.txt
python -m coverage run -m unittest discover -s tests -v
python -m coverage report --fail-under=90
python -m portfolio build
node --test tests/*.test.mjs
python -m pip wheel --no-deps --wheel-dir build/wheels .
```

See [domain review](STAFF_REVIEW_V2.md), [platform review](STAFF_PLATFORM_REVIEW.md), [package review](PACKAGE_REVIEW.md), and [machine-readable results](VALIDATION_RESULT.json). [GitHub Actions](https://github.com/Snuthakki21/synthetic-data-assurance-lab/actions) runs Python 3.11/3.14, frontend/build checks and an installed-package check before Pages publication.

## Browser and operating evidence

[Desktop view](screenshots/desktop.png) and [mobile view](screenshots/mobile.png) show the actual application interface. Each product was run in the browser and its successful execution was observed in history. Additional shared-flow checks saved a scenario, reloaded browser storage, recorded a native review and compared changed native inputs/results. The native stored run retained its earlier evidence review after later executions.

The Python source digest for the executed sample is `7c7ce7679f1056717cac4f2859a9fde10911ceff6c85035fd9292ad262e62403`. Reviewer manifests separately identify the actual files they examined. Executed reports preserve their own timestamp, input hash, source hash and model mode.

## Limits of this validation

These are automated tests and separate automated Staff Engineer reviews, not external human certification. Fixtures and held-out model examples are synthetic. Live model-provider contracts use controlled substitute responses in tests; no paid provider execution, enterprise benchmark or deployed production integration is claimed. Docker/Compose configuration is supplied and reviewed; Docker was unavailable in the verification environment, so container runtime behavior is not claimed as tested. The native application is documented as single-operator, with optional shared-token access rather than multi-user roles.
