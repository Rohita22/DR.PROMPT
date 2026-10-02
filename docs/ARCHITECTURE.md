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
- `evaluation`: provider-neutral model settings, visible/hidden executable test types, grader contracts and configurations, deterministic grader resolution, output evaluation orchestration, and evaluation outcomes.
- `execution`: the challenge-family boundary: `ChallengeExecutor` contract, normalized `ChallengeExecutionResult` with typed artifacts, explicit `ChallengeExecutorResolver`, `TextChallengeExecutor` (`LLMProvider` + `EvaluationEngine`), and the reusable `ApplicationChallengeExecutor`.
- `application`: the APPLICATION family's versioned configuration, strict agent edit protocol, deterministic layout checks, and its `CodingAgent`, `Workspace`, `ApplicationEvaluator`, and `StarterPreviewReader` ports.
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

`GetChallengeLeaderboardUseCase` resolves the current published challenge version and its exact model identifier/configuration version, then calls the narrow `LeaderboardReader` port. `PostgresLeaderboardRepository` uses PostgreSQL window functions: it ranks submissions inside each user, keeps position one, then ranks those user-best rows globally. The query never depends on score-driven `user_progress.best_submission_id`, and no leaderboard table or cache is maintained. Optional authentication adds only the verified current user's independently queried position.

```text
public/optional-auth request → active PlayableChallenge
                             → LeaderboardReader
                             → comparable authoritative submissions
                             → per-user row_number → global row_number
                             → safe paginated leaderboard response
```

`GetCurrentUserProfileUseCase` combines verified local identity with a `ProfileReader` snapshot and the pure level policy. `PostgresProfileRepository` derives XP from the append-only ledger, completion/stars from current published challenge progress, best position with the canonical leaderboard window ordering, and five recent owned submissions with per-submission XP totals. It uses a fixed number of aggregate queries rather than one query per challenge and persists no duplicate profile counters.

```text
verified current user → ProfileReader → ledger/progress/submission aggregates
                                    → active leaderboard window ranks
                      → level policy → safe current-user profile
```

The schema uses opaque domain strings for stable challenge IDs and public version labels, plus UUID primary keys for version rows, examples, tests, and submissions. A unique `(challenge_id, version)` constraint keeps labels such as `1` meaningful per challenge. See [DATABASE.md](DATABASE.md) for the schema, migration, and seed workflows.

## Provider and evaluation boundaries

Evaluation is a dedicated domain because it combines security-sensitive datasets, untrusted model output, grader strategies, and result sanitization. Treating it as route logic would make hidden-test leakage and policy duplication more likely.

The asynchronous `LLMProvider` port prevents application code from depending on Groq. It accepts a provider-neutral `LLMExecutionRequest` and returns an `LLMExecutionResult`; neither exposes SDK types. A request may carry a provider-neutral strict JSON Schema output specification, while model configuration may select a provider-neutral reasoning effort. `infrastructure/llm/GroqProvider` is the first adapter and translates these values into the official SDK's `response_format`, `reasoning_effort`, `reasoning_format`, and `max_completion_tokens` fields. Explicit factory wiring constructs it from validated backend settings, while reusable test fakes keep application tests deterministic and free. Other providers can be introduced without rewriting use cases.

Groq-specific imports are confined to `infrastructure/llm`. The factory creates a fresh async client with the configured timeout and SDK retries disabled; it does not create a global client or make a request during application startup. Provider exceptions, refusals, length-truncated completions, and malformed structured responses are translated into project-owned errors before crossing the infrastructure boundary. The adapter locally revalidates returned structured JSON even though Groq strict mode constrains decoding.

FastAPI dependency providers explicitly wire request-scoped PostgreSQL repositories, the Groq-backed `LLMProvider`, evaluation engine, the TEXT/APPLICATION executor resolver, and separate Run/Submit use cases. The hidden reader is held only by `TextChallengeExecutor`, used only by `execute_hidden` (Submit), and not represented in any API schema. Tests override use-case dependencies with in-memory repositories and `FakeLLMProvider`; they never construct a Groq client or require API or database credentials.

Submit also depends on the domain `PromptTokenCounter` port and pure `ScoringService`. `infrastructure/tokenization/GptOssPromptTokenCounter` implements the port with OpenAI's `o200k_harmony` ordinary-text encoding. Its official `o200k_base` vocabulary is stored and hash-verified locally, so scoring makes no runtime tokenizer download or provider request. The adapter counts only the player-authored prompt, not the system wrapper, test input, or provider usage totals.

## Challenge execution

### Implemented: executor boundary and TEXT executor

Each `ChallengeVersion` carries a `ChallengeType` (`text`, `application`, `image`), persisted in `challenge_versions.challenge_type`. The five CONTROL foundations are `text`; Responsive Hero and Pricing Grid are `application`. Both are executable. IMAGE is not registered.

The `execution` domain (`app/domains/execution`) owns the family boundary:

- `ChallengeExecutor` is a protocol with two methods: `execute_visible` (backs Run) and `execute_hidden` (backs Submit). Both take a `ChallengeExecutionRequest` (the `PlayableChallenge` plus the player prompt) and return a `ChallengeExecutionResult`.
- `ChallengeExecutionResult` is the internal normalized outcome: `evaluation_score` (0–100, the normalized scoring input), `passed_checks`, `total_checks`, per-check `check_results`, and typed `artifacts`. TEXT uses `TextOutputArtifact`; APPLICATION uses typed changed-file, build, and screenshot artifacts. The result may describe hidden checks and is never serialized.
- `ChallengeExecutorResolver` is an explicit per-instance `ChallengeType → executor` mapping, copied at construction and built in `api/dependencies.py`. It has no global registry. An unregistered type raises `UnsupportedChallengeTypeError` (HTTP 503, `unsupported_challenge_type`); nothing falls back to text.
- `TextChallengeExecutor` holds the text-specific orchestration that used to live inside the use cases. It calls `LLMProvider` once per test case, sequentially and fail-fast, with the player prompt, test input, and the version's `ModelConfiguration`. It then grades with the existing `EvaluationEngine`. For TEXT, `evaluation_score` is exactly the pass-rate accuracy. `execute_hidden` loads the exact version's suite through `HiddenTestSuiteReader` and rejects a missing or mismatched suite before any model call. The executor also refuses non-TEXT versions itself.

```text
RunChallengeUseCase                    SubmitChallengeUseCase
  load challenge, access check           load challenge, access check
                                         count tokens, enforce hard limit
  resolver.resolve(challenge_type)       resolver.resolve(challenge_type)
  → TextChallengeExecutor                → TextChallengeExecutor
      .execute_visible                       .execute_hidden (loads hidden suite)
      → LLMProvider → EvaluationEngine       → LLMProvider → EvaluationEngine
  ChallengeExecutionResult               ChallengeExecutionResult
  → detailed visible RunChallengeResult  → ScoringService (evaluation_score as accuracy)
                                         → save_with_progression (submission, progress, XP)
                                         → aggregate-only SubmitChallengeResult
```

Run and Submit remain separate use cases with separate result types. The executor owns no HTTP, authentication, token counting, scoring, persistence, XP, unlocking, leaderboard, or profile behavior. Public API contracts still use `accuracy`; the application layer maps `evaluation_score` onto it.

Both use cases share a request-scoped resolver whose TEXT executor holds the hidden-suite reader. Run only ever calls `execute_visible`, which never touches that reader (asserted by tests). Hidden-suite access is reachable only through `execute_hidden`, which only Submit calls.

The admin `TestChallengeUseCase` still grades draft records directly with `LLMProvider` and `EvaluationEngine`, because drafts are not `PlayableChallenge`s and include their hidden cases inline. The builder also authors APPLICATION through a separate package configuration and the shared application executor. IMAGE remains unsupported.

### Implemented: Application Platform v1

```text
ChallengeExecutorResolver (api/dependencies.py)
  text        → TextChallengeExecutor          implemented
  application → ApplicationChallengeExecutor   implemented (two static packages)
  image       → none → UnsupportedChallengeTypeError (503)
```

`ApplicationChallengeExecutor` (`app/domains/execution/application.py`) depends only on domain ports in `app/domains/application/ports.py`:

```text
ApplicationChallengeExecutor
  → WorkspaceFactory.create(starter, editable_files)   LocalWorkspaceFactory: fresh OS temp dir
  → CodingAgent.apply_instructions(AgentTask)          LLMCodingAgent over LLMProvider;
                                                        strict JSON Schema request
  → parse_agent_edits (domain, pure)                   independent whole-file/security validation
  → Workspace.write_text                               allowlisted, existing, path-confined files
  → package policy validation → ApplicationEvaluator.inspect                       PlaywrightApplicationEvaluator:
                                                        fixed-argv build + headless Chromium
  → ApplicationCheckRegistry (domain, pure)                     deterministic checks over measured facts
  → ChallengeExecutionResult                           evaluation_score = passed / total × 100
                                                        artifacts: ChangedFiles, Build, Screenshots
  (workspace always deleted)
```

- `ApplicationChallengeConfig` lives on `ChallengeVersion.application_config`. It is required for APPLICATION and forbidden for other types. It names a repository-owned starter project, the editable files, a fixed build argument list, the build output, visible and hidden check IDs, and limits.
- Check logic lives in `app/domains/application/checks.py` as a per-instance trusted registry over selector-indexed `LayoutMetrics`. Registered package manifests define typed check parameters and measurement viewports. The browser only measures; it never decides.
- Adapters live in `app/infrastructure/application/`: `StarterProjectRepository` (explicit registered package loader under `backend/application_challenges/`), `LocalWorkspaceFactory`, `process.py` (fixed-argv subprocess, minimal environment, log sanitizer), `PlaywrightApplicationEvaluator` (the sync Playwright API in a worker thread, so it works under any event-loop policy), and `LLMCodingAgent`.
- Run and Submit stay separate use cases. Each branches only at result mapping: `ApplicationRunResult` (visible checks with labels, screenshots, build, changed files) or `ApplicationSubmitResult` (aggregates plus the desktop screenshot). Access checks, token counting, scoring, the persistence transaction, XP, and leaderboards are shared and unchanged.
- `GET /challenges/{slug}/starter-preview/{viewport}.png` serves committed starter screenshots through `GetStarterPreviewUseCase`.
- Settings: `APPLICATION_BROWSER_CHANNEL` (empty means Playwright's bundled Chromium; `chrome`/`msedge` use an installed browser). Node.js must be on PATH.

APPLICATION player execution is guarded before workspace creation. `ApplicationExecutionService` carries provider-neutral policy; its PostgreSQL adapter acquires a session advisory lock derived from the verified local user on a dedicated connection. Run and Submit share that lock, so one user has at most one in-flight APPLICATION execution while other users remain independent. Short transactions check/upsert kind-specific durable cooldown rows before execution; the advisory lock is released in `finally` and PostgreSQL also releases it if the connection is lost. No long database transaction spans model or browser work.

APPLICATION Submit additionally reserves a key hashed from `Idempotency-Key`, scoped by verified user and exact challenge version. A completed duplicate replays its stored safe result without executing the agent. Submission, progression, XP, and idempotency completion commit atomically. Infrastructure failures delete only the in-progress reservation so the same key can retry, while the already-recorded cooldown remains. A fresh orphaned reservation returns in-progress; after the configured 180-second stale window it may be replaced. Admin challenge testing is separately wired and does not use player limits.

### Planned — not implemented

- `ImageChallengeExecutor`.
- A real sandbox for agents that write executable code, durable artifact storage, live previews, a multi-step agent, and family-specific admin editors. See [CHALLENGE_TYPES.md](CHALLENGE_TYPES.md#deferred-decisions).

## Authentication boundary

```text
Browser → Supabase Auth → access token → FastAPI
                                      → JWKS signature/claim verification
                                      → local user synchronization
                                      → owned Submit use case
```

The application-facing `AccessTokenVerifier` returns only a typed `AuthenticatedIdentity`; raw claims and JWT library types remain in `infrastructure/auth`. `SupabaseAccessTokenVerifier` derives the issuer and JWKS URL from `SUPABASE_URL`, permits only configured asymmetric algorithms, verifies signature, expiration, issuer, audience, and subject, and caches public keys in process for ten minutes. An unknown key ID triggers one refresh to accommodate signing-key rotation.

FastAPI extracts bearer credentials and resolves a local user before constructing a Submit command. The command receives the verified local UUID explicitly. Run supports optional authentication for the first TEXT challenge, while progression-gated APPLICATION Run resolves the verified local user before its guard. The request schema rejects extra fields, so a browser cannot submit an owner ID.

## Frontend communication

The frontend calls the backend through `NEXT_PUBLIC_API_BASE_URL` and versioned `/api/v1` routes. The application uses `@supabase/ssr` for Google PKCE OAuth, email/password authentication, cookie-backed session restoration, and Next.js Proxy token refresh. It forwards the access token only in the `Authorization` header for authenticated API requests. Final pages reuse the shared paper/ink tokens, site navigation, typography, cards, controls, and responsive breakpoints in `globals.css`; feature behavior remains under `src/features`. As the API grows, FastAPI's OpenAPI document should become the source for generated TypeScript types rather than expanding handwritten schemas indefinitely.

## Admin authoring boundary

Admin transport routes validate typed authoring schemas and call dedicated application use cases. `PostgresAdminChallengeRepository` is the sole draft/version writer used by the builder; published versions are never edited in place. A challenge points to one active published version, while a newer draft can coexist for authoring. Publishing retires the previous active version and switches the pointer atomically; unpublishing clears the pointer without deleting content or player history.

```text
Admin browser → Next.js HttpOnly admin session → server-only BFF
              → X-Admin-Key → FastAPI admin dependency
              → admin use case → admin repository → PostgreSQL
```

The private `ADMIN_API_KEY` exists only in backend and Next.js server environments. Client authoring code calls same-origin `/api/admin/*` routes and never receives or attaches the key. Admin challenge testing composes the existing LLM provider, evaluation engine, token counter, and scoring service, but has no submission/progression repository dependency and therefore cannot award XP or affect leaderboards.

The builder supports TEXT and APPLICATION on the same draft/publish/version lifecycle. APPLICATION authoring selects trusted package defaults, check presets, screenshot presets, and narrower limits through typed controls. Admin tests use the shared executor without gameplay side effects. IMAGE remains unsupported.

## Application authoring boundary

See [APPLICATION_PLATFORM.md](APPLICATION_PLATFORM.md) for configuration → package registry → executor → agent/workspace → build → browser measurements → check registry → result. `ApplicationPackageLoader` is the storage port. Package policy owns structural settings; admin can narrow file/check selections, screenshot presets, and limits. PostgreSQL mapping and execution both revalidate configuration. Admin Test uses a transient playable view of the saved draft and the same executor, making one agent call and no gameplay writes.
