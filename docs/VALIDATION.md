# Standalone verification evidence

Checked at 2026-09-17T05:01:32.534575+00:00. These results come from commands executed inside this repository after export.

Runtime versions: Python 3.14.7; Node.js v25.9.0.

Standalone release verification: **PASS**. All recorded commands passed.

| Check | Observed result |
|---|---|
| Python unit and integration tests | 80 discovered; 78 executed; 2 skipped |
| Statement coverage | 635/640 (99.22%) |
| Branch coverage | 314/320 (98.12%) |
| Frontend tests | 31 discovered; 25 executed; 6 skipped |
| Built application discovery | synthetic_data_foundry |
| Installed project directories | synthetic_data_foundry |
| Installed UI templates | synthetic_data_foundry |
| Missing README targets | [] |
| Default input | Executed through the repository CLI; saved in `examples/report.json` |

Reproduce from the repository root:

```sh
python -m pip install -r requirements-dev.txt
python -m coverage run -m unittest discover -s tests -v
python -m coverage report --fail-under=90
python -m portfolio build --output dist
node --test tests/frontend.test.mjs
```

Application source SHA-256: `c401994ce85c6cb0bb217857567a12534d4cc8e3b807025f98c360493b178d54`.

Coverage includes this application and its shared Python runtime. Skipped tests exercise capabilities belonging to applications absent from this standalone repository. Provider transport tests use controlled doubles; these counts are not live-model accuracy measurements. The frontend suite exercises rendering, escaping, input binding and asynchronous state with controlled DOM/worker harnesses; it is not an exhaustive visual, accessibility or browser compatibility audit. Coverage measures executed code paths and does not establish semantic correctness.

See the solution-specific independent review linked in the README and the [shared runtime review](INDEPENDENT_RUNTIME_REVIEW.md) for review findings, repairs and limits.
