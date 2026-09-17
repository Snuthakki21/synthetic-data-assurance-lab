# Optional model integration and MCP

Local mode is the default. Deterministic calculations, validation and decision boundaries remain in Python. A supported live integration can propose a bounded interpretation or draft evidence-based prose; it cannot directly change trusted arithmetic or execute a production action. The project README identifies its exact AI seam. Inference Cost Lab deliberately remains a measured simulation and has no live inference-provider benchmark.

## Configuration

| Variable | Behavior |
|---|---|
| AI_PROVIDER | `openai` (default, OpenAI-compatible Chat Completions envelope) or `ollama` |
| AI_MODEL | Required explicit model identifier in live mode; no model is selected automatically |
| AI_BASE_URL | Defaults to `https://api.openai.com/v1` for openai or `http://127.0.0.1:11434` for ollama |
| AI_API_KEY | Bearer credential for the configured OpenAI-compatible provider; OPENAI_API_KEY is a fallback |
| AI_TIMEOUT_SECONDS | Per-call timeout, default 60 seconds, permitted range 1–180 |

Set these in the launching process environment. Never put keys in a scenario, static page, GitHub workflow or repository. The runtime does not read .env files automatically. HTTPS is required except for an explicit loopback endpoint; URLs containing credentials, queries or fragments are rejected and redirects are disabled. Endpoint selection is an operator responsibility. Compatible APIs must support the actual payload fields below; compatibility is not assumed from the provider's name.

For an existing local Ollama installation with a model already available:

```sh
export AI_PROVIDER=ollama
export AI_MODEL='YOUR_INSTALLED_MODEL'
python3 -m portfolio run PROJECT_ID --mode live
```

To use a remote compatible provider, set AI_PROVIDER, AI_MODEL, AI_BASE_URL if needed, and your API key using your normal secret-management method; then run the same command. `python3 -m portfolio serve --mode live` enables the server's optional integration for browser requests. The GitHub Pages/browser-worker version always uses local mode and never receives provider credentials.

## Request and failure contract

The openai adapter sends `/chat/completions` with JSON-object response format, `max_completion_tokens: 2000`, and `store: false`. It requires `finish_reason: stop`. The Ollama adapter sends `/api/chat` with the project schema, non-streaming output, temperature zero, `think: false` and `num_predict: 2000`; incomplete or length-truncated responses are rejected. A project's model compatibility and quality must be evaluated with the exact configured model; schemas alone do not establish factual correctness.

The runtime enforces a 100,000-character prompt limit, 1 MB provider response limit and schema subset validation without coercion. General application runs allow at most three calls. AI Evaluation Release Gate validates the full case input before calling a provider and supports 2–20 live cases with one call per case. Errors are reported as failed structured-output/provider operations; the caller must not silently promote a failed live run. Successful report provenance lists provider/model, status, elapsed time and available token usage; the key and raw provider response are not recorded there.

Cancellation of a browser HTTP request does not stop a server thread or a call already accepted by a provider. The per-call timeout still applies, and costs can still be incurred. Project-specific exact-phrase checks, bounded plans and grounded evidence IDs have documented limitations. Generated narrative requires review, even after schema validation. See the independent review report for what was actually tested with mocks versus a live provider; no blanket live-model quality claim is made.

## Integration evidence

On 2026-09-17, a coordinator-executed local Ollama call using `gemma4:26b-mlx` completed the shared request/response path for AI Investment Planner in 6,437 ms (713 prompt tokens and 195 output tokens). The revised result correctly identifies 19 person-months of effort. This is a successful transport and structured-output smoke test, not a quality benchmark. An initial draft had mislabeled person-month effort as elapsed months; the prompt was corrected to label units explicitly and a second live call verified the revised wording. That first failure illustrates why narrative still requires review. Other project-specific model seams were tested with controlled doubles unless their own review explicitly records a live call.

## Read-only MCP tools

```sh
python3 -m portfolio mcp
```

Configure an MCP client to launch that command with this repository as its working directory and a Python 3.11+ executable. This is a newline-delimited JSON-RPC stdio transport advertising protocol version 2025-11-25. It implements initialize, ping, tools/list and tools/call; it is not a general remote MCP service or complete implementation of every protocol feature.

Each installed project is one tool. Tool arguments are an optional `payload` object; no argument uses the original default. MCP always runs local algorithms, even when provider environment variables are present. Calls do not write to production systems. The transport caps input frames at 256 KB, validates JSON-RPC request identifiers, rejects nonfinite JSON and returns no response for notifications. Errors are returned as protocol errors or tool results with isError true as appropriate.

Client configuration formats differ; use the client's documentation for its command/cwd syntax. Keep logs off stdout, which is reserved for protocol frames. The implementation follows the [MCP basic protocol](https://modelcontextprotocol.io/specification/2025-11-25/basic); compatibility with a particular external client requires its own smoke test.
