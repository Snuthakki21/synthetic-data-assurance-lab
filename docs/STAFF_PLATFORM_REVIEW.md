# Independent automated Staff Engineer review — workspace platform

Reviewed 2026-09-17T06:00:12.138991+00:00.

**Verdict: accepted for the documented single-operator deployment boundary, after remediation and independent retest.** This is an automated review by a separate reviewer persona that did not author the platform implementation. It is not an external human audit, security certification or evidence of production deployment. The reviewer wrote regression tests and reported defects; the implementation owner changed source code.

## Scope

The review covered native SQLite scenario/revision persistence, execution reservation and idempotency, run comparison, review state and optimistic version checks, audit chaining, backup and recovery, API command validation, Host/Origin/token guards, static-file boundaries, browser repository and storage contracts, native transport, async workspace presentation, and the shared application/CLI/server integration.

Product-specific domain algorithms are outside this shared-platform verdict and have separate project reviews. Bundled interpreter binaries and third-party dependencies were not source-audited here. IndexedDB transaction code was inspected; repository contract tests use the deterministic memory adapter. Actual browser rendering and public deployment verification are separate release checks.

## Findings and verified remediation

| Finding | Reproduction and impact | Remediation and retest |
|---|---|---|
| Archive race at execution reservation | Archiving after the service read but before SQLite reservation still permitted a new execution. | The write transaction checks archived state. Independent test interleaves archive before reservation and confirms no execution/audit reservation is created. |
| Malformed scenario identities crossed the storage boundary | An execution command with list/dict scenario identity reached SQLite binding and raised an internal ProgrammingError. | Repository identity validation now rejects invalid values before SQL. Direct API and actual HTTP tests return bounded 400 responses and the server remains usable. |
| Out-of-order run inspection | A slow earlier inspection could overwrite the newer selected run and its review panel. | Generation checks preserve the newest selection. Deferred-promise regression verifies both selected state and rendered panel. |
| Out-of-order or destroyed comparison | An older comparison could overwrite a newer result, or publish after the controller was destroyed. | Comparison generation and lifecycle checks suppress stale completion. Both cases have independent regressions. |
| HEAD bypassed static-file containment | GET rejected an out-of-root symlink, but inherited HEAD exposed its file size and modification metadata with status200. | The shared send_head boundary now rejects it for either method; actual HTTP HEAD regression returns404. |
| Duplicate metric suffix collision | Labels Amount, Amount [3], Amount caused the generated suffix to overwrite an existing metric in native and browser comparisons. | Collision-safe names reserve original labels. Independent Python and JavaScript regressions preserve all three metrics. |
| Backup connection lifetime | sqlite3 connection context managers did not explicitly close the source and destination handles. | Both connections use explicit closing contexts. Independent backup verifies historical revisions, completed runs, audit consistency and refusal to overwrite existing output. |
| Scalar control event synchronization | A typed control could remain visually changed while executable JSON was stale until blur/change fired. | Input and change events now both update the executable JSON. An independent test types a scalar value and verifies JSON before a blur event. |
| Browser fetch receiver | Native transport previously invoked the captured fetch function as a client method, causing Illegal invocation in an actual browser. | Transport now invokes the function without a client receiver; a separate independent strict-receiver regression passes. |
| Unsupported IPv6 configuration | IPv6 loopback was accepted despite an IPv4 server socket/origin implementation. | Configuration now rejects ::1 with an actionable IPv4 loopback instruction. |

Additional inspected improvements include exact saved-scenario binding in browser/native execution, archived-scenario checks, protection against inherited prototype lookups, stale revision rejection, and complete browser export with explicitly bounded native export/backup semantics.

## Verification actually performed

- **42 Python workspace tests passed**, including **11 independent review tests**. These exercise native persistence, concurrent review CAS, idempotent immutable scenario revisions, actual ephemeral HTTP, backup consistency and the reproduced defects.
- **23 JavaScript workspace tests passed**, including **12 independent review tests**. These exercise async completion ordering, destroyed-controller behavior, exact decimal differences, detached/atomic revisions, failed persistence, failed-run review rejection, collision-safe comparison and saved-revision binding.
- A separate real CLI/server integration started the native application on an ephemeral loopback port, completed a persisted domain execution through the REST API, verified the audit through the CLI, created a nonempty SQLite backup and terminated the server cleanly.
- No source changes were made by this reviewer. No paid model/provider call or production-system write was required for these checks.

## Authority and remaining boundaries

Reviewer identifiers are operator labels, not authenticated multi-user identities. An approved stored execution does not authorize a production action. The native audit hash chain detects inconsistent records relative to a trusted checkpoint; a database administrator can rewrite an unsigned database. Browser records remain in that browser and are editable by its operator. Browser retention limits and native backup/export scope must remain explicit in product documentation. The shared access token protects a configured service, but does not create role-based authorization or tenancy.

The final release must still execute each repository's full domain tests, build, public CI and browser workflows. This review does not substitute for those integration checks or claim a coverage percentage that was not measured here.

## Reviewed source snapshot

Hashes identify the exact files inspected and retested. Later source changes require corresponding review or documented follow-up.

| File | SHA-256 |
|---|---|
| `app/platform/__init__.py` | `52d8180a549daabdb8641eeb305918d73f52f33254be9955620b19d16b37be66` |
| `app/platform/api.py` | `e64b9d623ef2bfe85d5dbbf0d8163a1aab67dca476d462834dab20f8cf1d6264` |
| `app/platform/cli.py` | `69b64c99d7bf2c7c93793e49f6147d215a49cf21d72c21b8bbec45fe979f5abd` |
| `app/platform/comparison.py` | `e504a89b8fa18590a1a969865f4108a2e23ef056224df70bd81e81af04174952` |
| `app/platform/config.py` | `cf30b03a677600d9113c0672a37461214476ad79b8bea8c5f20c5d311dabc9b7` |
| `app/platform/errors.py` | `a6d7998498287375b1b03fe129f51a63a19c5c9015844f129ee089051bd44776` |
| `app/platform/http_server.py` | `59fe6c6ea540d8ddd3fce41a4aececaf78c338037caf4bded4326f5f10026100` |
| `app/platform/migrations.py` | `da30ce5e1068e9b7937736308d5c76de411d9f7632820c0ca6368b9b3ac3dbb5` |
| `app/platform/models.py` | `4de89eb9385396175d04ecd5a956eba9f0a9edee51e917a7ae47f45b946a4f12` |
| `app/platform/repository.py` | `3197b536ce2aa60272ab398c7945656f6f7f10c7966309ab95c108048449052b` |
| `app/platform/service.py` | `2b2746d7dd18a93b30cd4391e596ba7353fcf16efc49eb1d1bdc97b82ee093d1` |
| `portfolio/__main__.py` | `ddeddfc8ddbbfc66b3df188ba1aa6cb847736a2cf6121bf3e61742219e0de4fe` |
| `portfolio/server.py` | `d1bf656da3aa68f42b19cc3f2e98e0a9c505dd99235bf88e1d43c1d5b22eb6e2` |
| `tests/test_workspace_independent.py` | `63736091f0fbe2b33e97ed3f2c71407695004455347f1cdae7a4b2e1fa80688a` |
| `tests/workspace-independent.test.mjs` | `110b13e51e0417a6f12a8d517c71863da668f13a6b0f21fed1976e711406eda9` |
| `web/app.js` | `1632e70f99c677914099c5a1104ac14af228eef90a51758ca9e138eb3effd783` |
| `web/workspace/client.js` | `c655a583aa9d675270440d9db223f898eb94360ab4863d4077565facd67c0880` |
| `web/workspace/contracts.js` | `52689555b6bc4556b510383f51d56c597eca61715e0c89841fb03ca979dfe3fd` |
| `web/workspace/controller.js` | `d400e3d9427ee582dc117292b3db29447a5369781437060ba7266d96283b0585` |
| `web/workspace/repository.js` | `65dc561d4ee9394dff1a7cc27362db7eb696937c4e0739f33c4e822ffe472a0e` |
| `web/workspace/storage.js` | `fe6547911e5a07233e47ace2c2606381c70a78721d64c6be8f8ffee0df3304fa` |
