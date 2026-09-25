# Architecture

## Monorepo

`frontend/` and `backend/` are separately runnable applications in one repository. `docs/` holds decisions shared by both. The system is a modular monolith: domain boundaries are explicit, while deployment and operational complexity remain low.

## Responsibilities

The Next.js frontend renders the experience, gathers user input, and presents API results. It must not contain grading, scoring, authorization, or hidden-test logic. Shared UI follows shadcn/ui conventions under `src/components/ui`; product capabilities belong under `src/features`.

FastAPI is the HTTP transport. Routes validate HTTP input, invoke application use cases, and serialize results. Pydantic defines request and response boundaries. Business policy belongs in domain modules, not routes.

The first gameplay vertical slice follows this boundary directly: the challenge Run route maps HTTP data into `RunChallengeCommand`, invokes `RunChallengeUseCase`, and maps its application-owned result into a visible-test response. The use case depends on `ChallengeReader`, `LLMProvider`, and `EvaluationEngine`; it has no FastAPI or Groq dependency.

## Backend dependency direction

```text
API / transport → application use cases → domain logic and ports
                                           ↑
                              infrastructure adapters
```

Domain modules must not import FastAPI, databases, authentication SDKs, or vendor clients. Application code coordinates domain behavior through ports. Infrastructure implements those ports and is wired at the application boundary.

## Domain boundaries

- `challenges`: stable challenge identities, immutable playable versions, explanatory examples, and publication state.
- `evaluation`: provider-neutral model settings, visible/hidden executable test types, grader contracts and configurations, deterministic grader resolution, output evaluation orchestration, and evaluation outcomes. Future application use cases will compose this with model execution for Run and Submit.
- `submissions`: submission records and lifecycle.
- `scoring`: validated challenge-specific weights and thresholds; future scoring calculations remain pure domain logic.
- `progression`: future stars, XP, and unlock rules.
- `leaderboard`: challenge-specific ranking behavior.

The small `system` domain owns the health use case. `Challenge` is the stable catalog identity, while `ChallengeVersion` is the exact playable configuration to which future submissions will refer. Server-only `HiddenTestSuite` objects are linked by challenge-version ID rather than embedded in `ChallengeVersion`; this keeps hidden data out of the commonly consumed definition by construction.

`PlayableChallenge` pairs a stable identity with its current published version while enforcing their IDs and publication state. The minimal `ChallengeReader` port retrieves this view by slug. `infrastructure/challenges/InMemoryChallengeRepository` currently serves one immutable CONTROL challenge and is replaceable without changing the Run use case.

## Provider and evaluation boundaries

Evaluation is a dedicated domain because it combines security-sensitive datasets, untrusted model output, grader strategies, and result sanitization. Treating it as route logic would make hidden-test leakage and policy duplication more likely.

The asynchronous `LLMProvider` port prevents application code from depending on Groq. It accepts a provider-neutral `LLMExecutionRequest` and returns an `LLMExecutionResult`; neither exposes SDK types. `infrastructure/llm/GroqProvider` is the first adapter and translates the existing challenge `ModelConfiguration` into an official Groq SDK request. Explicit factory wiring constructs it from validated backend settings, while reusable test fakes keep application tests deterministic and free. Other providers can be introduced without rewriting use cases.

Groq-specific imports are confined to `infrastructure/llm`. The factory creates a fresh async client with the configured timeout and SDK retries disabled; it does not create a global client or make a request during application startup. Provider exceptions and malformed responses are translated into project-owned errors before crossing the infrastructure boundary.

FastAPI dependency providers explicitly wire the in-memory challenge reader, Groq-backed `LLMProvider`, evaluation engine, and Run use case. Tests override the use-case dependency with `FakeLLMProvider`; they never construct a Groq client or require an API key.

## Frontend communication

The frontend calls the backend through `NEXT_PUBLIC_API_BASE_URL` and versioned `/api/v1` routes. Its current handwritten health type is intentionally tiny. As the API grows, FastAPI's OpenAPI document should become the source for a generated TypeScript client/types so schemas are not manually duplicated.
