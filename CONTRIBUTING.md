# Working agreement

This is an independently runnable engineering application. Use original synthetic fixtures only. Do not copy employer code, customer data, or private repositories. Do not describe demo results as production results or claim compliance certification.

## Project contract

Each `projects/<snake_case_id>/project.py` exports `META`, `default_input()`, and `run(payload, context=None)`.

`META` contains `id`, `title`, `category`, `buyer`, `question`, `promise`, `description`, `principal`, `director`, `patterns` (strings), `architecture` (ordered strings), `risks` (strings), `limits` (strings), and `demo_inputs` (list of `{label, payload}` full input examples). Add `flagship` (bool) and `order` (display order).

`run` validates input, raises `ValueError` for unsupported/invalid data, and returns a JSON-serializable object containing `summary` (plain-English decision), `metrics` (list of `{label, value, unit}`), `evidence` (list of plain-English strings), `next_actions` (strings), and `details` (dict of inspectable results). Algorithms must operate on input, not return hardcoded successes. Output must explicitly disclose synthetic/local baselines and uncertainties. No network, shell execution, or production writes from project code.

For optional real model calls, use `context.generate_json(task=..., data=..., schema=...)`. It returns a validated dict in live mode and `None` in local mode; never interpret None as real model output. Context also has `mode` (local or live). Use JSON Schema objects with types, required keys and additionalProperties false. Validate model-selected actions and citations against allowlists before use. Avoid model-generated SQL/code execution. Default local algorithms must be useful without API keys.

Each project owns its README (executive brief, running example, architecture Mermaid, decision/tradeoff, measurable evaluation, limits, production roadmap), original fixtures, and `tests/test_<id>.py` using unittest. Tests must cover expected behavior, meaningful failure cases, and input changes. Keep runtime, UI, documentation and tests consistent with the declared project contract.

Target Python 3.11+ with standard library only for the default runner. Keep core runnable offline. Optional provider uses HTTPS; no credentials in the browser. The final website presents executed fixture reports, explicitly labeled, and local server allows fresh runs.
