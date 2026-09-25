# Architecture

## Monorepo

`frontend/` and `backend/` are separately runnable applications in one repository. `docs/` holds decisions shared by both. The system is a modular monolith: domain boundaries are explicit, while deployment and operational complexity remain low.

## Responsibilities

The Next.js frontend renders the experience, gathers user input, and presents API results. It must not contain grading, scoring, authorization, or hidden-test logic. Shared UI follows shadcn/ui conventions under `src/components/ui`; product capabilities belong under `src/features`.

FastAPI is the HTTP transport. Routes validate HTTP input, invoke application use cases, and serialize results. Pydantic defines request and response boundaries. Business policy belongs in domain modules, not routes.

The first gameplay vertical slice follows this boundary directly. Run and Submit routes map HTTP data into distinct commands, invoke distinct application use cases, and map application-owned results into purpose-specific responses. `RunChallengeUseCase` returns detailed visible-test feedback. `SubmitChallengeUseCase` returns aggregate fields only. Neither use case depends on FastAPI, Supabase, or Groq.

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
- `submissions`: framework-independent authoritative submission records and the minimal persistence port.
- `scoring`: validated challenge-specific weights and thresholds, a provider-neutral prompt-token counter port, and pure efficiency/final-score/star calculations.
- `progression`: pure XP milestone policy, monotonic per-challenge progress, and ordered challenge-access calculation.
- `leaderboard`: challenge-specific ranking behavior.
- `auth`: verified external identities, local application users, and authentication/user repository ports.

The small `system` domain owns the health use case. `Challenge` is the stable catalog identity, while `ChallengeVersion` is the exact playable configuration to which future submissions will refer. Server-only `HiddenTestSuite` objects are linked by challenge-version ID rather than embedded in `ChallengeVersion`; this keeps hidden data out of the commonly consumed definition by construction.

`PlayableChallenge` pairs a stable identity with its current published version while enforcing their IDs and publication state. The minimal async `ChallengeReader` port retrieves this view by slug. A separate server-side `HiddenTestSuiteReader` retrieves hidden cases by exact challenge and version identity. PostgreSQL adapters implement both ports, while the in-memory implementations remain fast test doubles. The public reader never queries the hidden-test table.

## Persistence boundary

Runtime persistence uses SQLAlchemy 2.x async sessions with `asyncpg`. Alembic owns the version-controlled PostgreSQL schema. Supabase is the intended managed PostgreSQL host, but no Supabase SDK appears in application or domain code.

ORM rows live only under `infrastructure/database`. Explicit mappers reconstruct immutable domain objects, and repositories return ports rather than SQLAlchemy types. `PostgresChallengeRepository` reads public challenge/version content, `PostgresHiddenTestSuiteRepository` is the dedicated server-only hidden-data adapter, and `PostgresSubmissionRepository` commits completed authoritative submissions. Submit considers persistence part of success: a failed save produces a sanitized system error rather than a non-durable score.

`PostgresUserRepository` synchronizes a verified external identity into the local `users` table. The `(auth_provider, auth_provider_user_id)` database constraint makes first access idempotent under concurrency. Submission ownership references the local UUID user; provider subject IDs are not used as application foreign keys.

`PostgresSubmissionRepository.save_with_progression` is the authoritative transaction boundary. It locks the local user, inserts the completed submission, updates the unique user/challenge progress row, appends only newly achieved XP milestones, calculates ledger-derived total XP, and commits once. `ProgressionService` owns the policy; the adapter owns SQL and transaction mechanics. Database uniqueness on progress and `(user, challenge, reason)` remains the final race-safety guard.

`ChallengeProgressionService` derives `locked`, `available`, `completed`, and `mastered` from published track ordering plus current-user best stars. `ChallengeAccessService` loads those inputs through narrow readers and protects detail, Run, and Submit before model execution. No unlock row is persisted. Anonymous users may access only the first published challenge; authenticated users advance by completing the previous challenge.

The schema uses opaque domain strings for stable challenge IDs and public version labels, plus UUID primary keys for version rows, examples, tests, and submissions. A unique `(challenge_id, version)` constraint keeps labels such as `1` meaningful per challenge. See [DATABASE.md](DATABASE.md) for the schema, migration, and seed workflows.

## Provider and evaluation boundaries

Evaluation is a dedicated domain because it combines security-sensitive datasets, untrusted model output, grader strategies, and result sanitization. Treating it as route logic would make hidden-test leakage and policy duplication more likely.

The asynchronous `LLMProvider` port prevents application code from depending on Groq. It accepts a provider-neutral `LLMExecutionRequest` and returns an `LLMExecutionResult`; neither exposes SDK types. `infrastructure/llm/GroqProvider` is the first adapter and translates the existing challenge `ModelConfiguration` into an official Groq SDK request. Explicit factory wiring constructs it from validated backend settings, while reusable test fakes keep application tests deterministic and free. Other providers can be introduced without rewriting use cases.

Groq-specific imports are confined to `infrastructure/llm`. The factory creates a fresh async client with the configured timeout and SDK retries disabled; it does not create a global client or make a request during application startup. Provider exceptions and malformed responses are translated into project-owned errors before crossing the infrastructure boundary.

FastAPI dependency providers explicitly wire request-scoped PostgreSQL repositories, the Groq-backed `LLMProvider`, evaluation engine, and separate Run/Submit use cases. The hidden reader is consumed only while constructing Submit and is not represented in any API schema. Tests override use-case dependencies with in-memory repositories and `FakeLLMProvider`; they never construct a Groq client or require API or database credentials.

Submit also depends on the domain `PromptTokenCounter` port and pure `ScoringService`. `infrastructure/tokenization/GptOssPromptTokenCounter` implements the port with OpenAI's `o200k_harmony` ordinary-text encoding. Its official `o200k_base` vocabulary is stored and hash-verified locally, so scoring makes no runtime tokenizer download or provider request. The adapter counts only the player-authored prompt, not the system wrapper, test input, or provider usage totals.

## Authentication boundary

```text
Browser → Supabase Auth → access token → FastAPI
                                      → JWKS signature/claim verification
                                      → local user synchronization
                                      → owned Submit use case
```

The application-facing `AccessTokenVerifier` returns only a typed `AuthenticatedIdentity`; raw claims and JWT library types remain in `infrastructure/auth`. `SupabaseAccessTokenVerifier` derives the issuer and JWKS URL from `SUPABASE_URL`, permits only configured asymmetric algorithms, verifies signature, expiration, issuer, audience, and subject, and caches public keys in process for ten minutes. An unknown key ID triggers one refresh to accommodate signing-key rotation.

FastAPI extracts bearer credentials and resolves a local user before constructing a Submit command. The command receives the verified local UUID explicitly. Run remains anonymous. The request schema rejects extra fields, so a browser cannot submit an owner ID.

## Frontend communication

The frontend calls the backend through `NEXT_PUBLIC_API_BASE_URL` and versioned `/api/v1` routes. A temporary client-side test harness uses `@supabase/ssr` for PKCE OAuth, cookie-backed session restoration, and Next.js Proxy token refresh. It forwards the access token only in the `Authorization` header for `/me` and Submit. As the API grows, FastAPI's OpenAPI document should become the source for generated TypeScript types rather than expanding handwritten schemas indefinitely.
