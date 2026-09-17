# Independent installed-package review

Reviewed 2026-09-17T06:03:54.975640+00:00. This product-specific extract records the separate automated reviewer's results for **synthetic-data-assurance-lab**.

**Verdict: installed-wheel execution and asset verification passed.** The reviewer built a wheel from isolated staging, installed it into its own target, and ran the `application` console entry point outside the source checkout. Default and explicit project execution, project listing, and static build all passed. The build executed 4 scenarios and contained exactly one product.

The wheel retained every source fixture (4 separate files; other scenarios may be embedded in the adapter), the modular application source and all eight checksummed runtime assets, including Pyodide and CPython licenses. Package metadata has no personal Author or Author-email field.

The first packaging pass found that an extensionless third-party license was omitted. Explicit LICENSE/NOTICE/COPYING package-data patterns corrected this; the reviewer rebuilt, reinstalled and verified the resulting artifact.

Reviewed artifact: `synthetic_data_assurance_lab-2.0.0-py3-none-any.whl`. The machine-readable [validation record](VALIDATION_RESULT.json) retains the independent artifact evidence. CI repeats installed-package execution on the published source; the review artifact itself is a snapshot, not a claim that subsequent document or stylesheet edits were inside the same wheel.

## Deployment review boundary

The Dockerfile uses Python 3.14, builds source/assets before switching to an unprivileged UID/GID, owns its workspace directory and has a local health probe. Compose binds the host port to loopback, requires an operator-supplied token, keeps SQLite in a named volume, drops Linux capabilities and enables no-new-privileges. Open the exact configured origin; remote access requires the documented trusted HTTPS reverse proxy.

Docker was unavailable, so image build, container startup, named-volume permissions and restart behavior were **not runtime-tested**. Native CLI/server/SQLite/backup integration was exercised separately in the [platform review](STAFF_PLATFORM_REVIEW.md). Each product must be installed in its own virtual environment because its `app`, `projects`, `portfolio` and `web` namespaces belong to that standalone distribution.
