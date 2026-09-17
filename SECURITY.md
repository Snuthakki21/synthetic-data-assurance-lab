# Security scope and reporting

This is a reference application with original synthetic fixtures. Its local algorithms do not connect to production systems. The included HTTP server binds to 127.0.0.1 and is intended for one operator on a trusted machine; it has no user authentication, TLS termination, tenant isolation, durable audit store or production availability controls. Do not expose this development server through a public proxy or change its binding as a deployment shortcut.

Model integration is opt-in and server-side. In live mode, the selected project sends the task's evidence to the configured provider. Supply only data you are authorized to send there. Keep provider keys in process environment variables, never in browser code, input JSON, commits or GitHub Pages. The runtime does not automatically load .env files. A canceled browser request can leave an already-started server/provider call running.

Input limits, schema checks, scoped decisions and grounded identifiers reduce specific failure modes. They do not prove immunity to prompt injection, data inference or incorrect generated prose. See the project's README and independent review for its actual boundaries. Model output never grants permission to perform production actions.

For a suspected vulnerability, use this repository's **Security → Report a vulnerability** when private vulnerability reporting is available. Do not put credentials, personal data or exploitable production details in a public issue. For a non-sensitive defect, open an issue with a minimal synthetic input, expected and actual behavior, Python/browser version and the source commit. There is no promised response SLA.

Only the current main branch is maintained in this portfolio. Dependency/action updates require tests and review. The repository MIT license covers original project code; bundled third-party assets retain their own licenses (see docs/THIRD_PARTY.md).
