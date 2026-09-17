# Independent automated Staff Engineer review: shared application runtime

Reviewed on 2026-09-17 by the non-authoring portfolio-strategy agent. The reviewer did not implement or remediate these shared modules. Review scope: provider/context runtime, project registry, loopback HTTP server, static packaging, JSON-RPC/MCP dispatch and command-line interface. The dedicated Staff Engineer skill perspective was applied by an independent agent; this is not a human sign-off.

## Findings and verified repairs

- **SHR-01 · P2 · Resolved — The generic three-call cap prevented the eight-case release suite from completing in live mode.** A mocked OpenAI-compatible response was supplied for each default case. The author now preflights release suite size, caps it at 20 and assigns its context budget to the case count. The reviewer independently observed all eight calls and complete results. Other projects retain the smaller general budget. The release author separately moved all case validation before the first provider call; that application change was cross-reviewed by the operations agent.
- **SHR-02 · P2 · Resolved — Huge JSON integers raised OverflowError during schema validation.** `validate_schema(10**400, {'type':'number','maximum':10})` now raises the documented ValueError. Integer validity no longer depends on conversion through floating point.
- **SHR-03 · P2 · Resolved — Invalid JSON-RPC identifiers and nonfinite JSON could break the MCP stream.** An input frame with `id: NaN` followed by a valid ping previously reached invalid serialization. The author now rejects nonfinite JSON while parsing and invalid request identifier types at dispatch. Independent subprocess tests observe parse error -32700, then a valid response to the second frame with exit code 0. Null/Boolean/object/array/fractional request IDs are rejected; notifications remain silent. The permitted string/integer, non-null request IDs match the [MCP basic protocol](https://modelcontextprotocol.io/specification/2025-11-25/basic).
- **SHR-04 · P2 · Resolved — A malformed provider envelope escaped the controlled failure boundary.** An empty `choices` list previously caused IndexError. The provider now records a failed call and raises ProviderError. Independent mock transport regression passes.

## Architecture and security checks

The reviewer inspected the actual source rather than inferring behavior from documentation. Provider calls use explicit live configuration, bounded timeouts and call budgets; schema checks gate structured output. Network redirects are restricted and local mode does not request an API. The loopback server validates Host/Origin and content type for execution requests and caps payload size. Tests start an ephemeral local server and observe 403 for an untrusted Origin, 415 for unsupported content type, and 200 for health. This is a local development server, not an authenticated internet service.

The registry rejects non-object/oversized input and unknown identifiers. The builder test packages a controlled temporary application and checks expected project source inclusion and bytecode exclusion. The CLI test observes exit code 2 with a concise unknown-project error and no traceback. JSON-RPC tests also verify handshake, tool inventory and unknown-action behavior. No external model was called in this review; provider envelopes were mocked.

## Reproducible verification

```sh
python3 -m unittest tests.test_runtime tests.test_staff_review tests.test_shared_integration -v
```

**59 tests passed:** nine author tests, ten independent reviewer tests and 40 additional non-author integration tests, exit code 0. The earlier 119-test scoped pass was followed by an earlier full-source checkpoint of 338 passing tests with 99.70% combined statement/branch coverage. Shared runtime/provider, registry, MCP and server each measured 100%; build measured 98.11% and CLI 95.16%. The independent file is portable to a single-project export: the release-specific integration test explicitly skips when that project is absent; that skip must not be reported as an executed live test.

| Source artifact | SHA-256 |
|---|---|
| portfolio/runtime.py | `d2ec7aa6f4e6e0a499a34d14871dfaa5a70d041ceda76b67077e9b29aec4911f` |
| portfolio/registry.py | `087b922dd15b54e9d38a6969338d9e4893e2266f91d23eab2d506d17204dc087` |
| portfolio/server.py | `aadf6eaa39d02b7a3d551420995ccb7d9dba03d1123cf03d16cb0cd33eb4be22` |
| portfolio/build.py | `7cbd7b25214ce0f26bd6da029c5874f1814f23bb0445bee28022a5fb8878d550` |
| portfolio/mcp.py | `2602f84f7df125b202bf134294aa50d3cb69f14c22f2d497312ffab3f439baec` |
| portfolio/__main__.py | `9e4413998cb272861e5e863b28346f63f1f07718d6c8d0541e37018dac35d472` |
| tests/test_runtime.py | `6cab7605aab74f30f03a971aa70e0079d7150f225f2083db11fa2a43ac0bead1` |
| tests/test_staff_review.py | `80cd659804559b56b53535f2c5c04563f37a457bbd56676ff9d2010db88a45b1` |

The additional integration suite independently exercises nested JSON enum/const Boolean-versus-number distinctions, optional enclosing JSON fences, malformed/incomplete/oversized provider responses, timeout and call budgets, HTTP error cleanup, CLI paths, registry contracts, MCP framing and the loopback server. Its source SHA-256 is `cff3d2515f9b998e27af50ead765d2c618ed3086ddc28a80634d7a258d9603c9`. The reviewer executed these tests and inspected the related runtime changes; the integration suite was authored by the non-authoring data agent.

## Follow-up verification after the release-range correction

On 2026-09-17, the non-authoring data-architecture agent independently reran all 59 shared tests after the coordinating author changed release preflight to the effective 2–20 case range. Valid endpoints 2 and 20 pass; 1 is rejected before provider work. The current source/test hashes are recorded above. This focused current run measured 99.75% statement coverage and 98.37% branch coverage across the shared Python source. No provider service was called; HTTP envelopes used controlled transports. The earlier 338-test application collection metric is a historical checkpoint, not the test count of an individual exported repository. Each export includes its separately measured verification record.

## Verdict and remaining boundaries

**PASS for the reviewed local runtime and protocol contract at these hashes.** All reproduced findings were corrected by the author and independently retested. This is not frontend/Pyodide validation, penetration testing of a deployed service, real model quality evaluation, an uptime assessment or proof of complete protocol conformance. Reload/restart is expected after source changes. Public standalone exports must receive their own build and smoke checks after packaging.
