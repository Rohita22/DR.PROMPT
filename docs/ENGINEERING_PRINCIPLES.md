# Engineering Principles

**Every developer and coding agent must read this document before modifying the repository.**

1. Keep business logic out of FastAPI routes and React components.
2. Respect the dependency direction: transport → application → domain/ports; infrastructure implements ports.
3. Validate external input. Use Pydantic at backend boundaries and strict TypeScript in the frontend.
4. Prefer explicit types, cohesive modules, single responsibilities, and pure functions for grading, scoring, calculations, and transformations. Avoid `any` and duplicated policy.
5. Isolate vendor-specific integrations in adapters. Depend on abstractions for LLMs, persistence, and authentication when an external boundary exists.
6. Create abstractions only for a present architectural boundary; do not over-engineer speculative features.
7. Remain a modular monolith. Do not introduce microservices, Redis, Celery, Kafka, RabbitMQ, Redux, or similar machinery without a demonstrated requirement.
8. Integrate new work into existing modules. Avoid unrelated refactors and unnecessary dependencies.
9. Test observable behavior rather than implementation details. Automated tests must use fake or mock LLM providers and never call paid/external model APIs.
10. Keep security-sensitive work server-side. Hidden tests are never serialized, logged to clients, or included in frontend bundles.
11. The backend derives identity from validated authentication context; it never trusts a user ID supplied by a browser.
12. Keep credentials out of source control and browser-visible environment variables.
13. Prefer free/local development services during the MVP. Deployment and production infrastructure are separate decisions.
14. Update relevant documentation and verification commands with each architectural change.

