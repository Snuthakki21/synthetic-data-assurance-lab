# Design: synthetic_data_foundry

The canonical architecture and tradeoffs are in [README](../../../README.md). `project.py` exports `META`, `default_input()` and `run(payload, context=None)`. `run` validates the trust boundary, calculates local evidence, optionally requests structured model assistance, and returns summary, metrics, evidence, next_actions and details. Unsupported inputs raise ValueError.

The deterministic core owns acceptance decisions. Models only draft constrained proposals or explanations; selected fields/actions/citations are checked against computed allowlists. Model text remains untrusted and reviewable. No plugin or model may authorize execution through these projects.
