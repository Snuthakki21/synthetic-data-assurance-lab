# Development and release process

Requirements live in the product and domain documentation. The application layer orchestrates typed domain objects, domain policies, AI/evaluation components and a separate workspace platform. The browser template exposes the actual domain outputs. Deterministic calculations, optional model generation and measured evaluation are described separately; a generated explanation cannot silently replace the authoritative calculation.

A change is accepted only after applicable Python domain/unit/integration tests, browser logic tests, an executed static build and a separate automated Staff Engineer review. Reviewers add their own regression cases for reproduced issues. `STAFF_REVIEW_V2.md` covers this product's expanded domain scope; `STAFF_PLATFORM_REVIEW.md` covers the storage/API/shared interface. Reviews identify their scope and limitations, and are automated assessments rather than human certification.

CI runs Python 3.11 and 3.14 with branch coverage over `app`, `portfolio` and `projects`, enforces 90% combined coverage, builds executed browser examples and runs JavaScript tests. Publication depends on those checks. Optional live model contracts are tested with bounded substitute transports; passing those tests does not claim paid external-provider execution or quality on private enterprise data.

Contributor tools support implementation and review, but their availability is not a runtime dependency or a product capability. There is no fabricated development history, production adoption or compliance certification. See validation evidence for actual commands and observed results.
