# Evaluation

Evaluation will implement the product's Write → Run → Submit loop while enforcing a strict trust boundary.

## Run

`RUN` is implemented as an application use case. `RunChallengeUseCase` retrieves a published `PlayableChallenge` through the minimal `ChallengeReader` port, executes each `VisibleTestCase` independently through `LLMProvider`, associates generated text by test ID, and delegates all grading and aggregation to `EvaluationEngine`.

The three prototype tests execute sequentially for deterministic, easy-to-debug behavior. If a provider call fails, Run stops and propagates the project-owned provider error; infrastructure failure is never converted into a wrong player answer. Because visible examples are already public, the purpose-built Run response includes test inputs, model outputs, expected outputs, and stable failure reasons. This mode supports iteration and is not an authoritative score.

The initial in-memory challenge records a prompt hard limit, but the use case does not enforce it until an authoritative tokenizer is available. Character length is not treated as token count.

## Submit

`SUBMIT` evaluates the prompt against hidden tests stored and loaded only on trusted server infrastructure. The browser sends the prompt, but never receives hidden inputs, expected outputs, database records, or revealing grader configuration. The evaluation use case returns only a purpose-built sanitized result such as aggregate tests passed, accuracy, efficiency, and final score.

The intended flow is:

```text
Browser → FastAPI → Evaluation use case → LLMProvider
                                      ↘ server-only test repository
                    grader → scorer → sanitized response → Browser
```

DTOs for public challenge data, visible run results, internal evaluation data, and submitted results must be distinct. Do not reuse an internal persistence model as an API response. This makes accidental hidden-test serialization difficult.

The implemented domain makes the distinction explicit:

- `VisibleExample` is explanatory challenge content and is never implicitly executable.
- `VisibleTestCase` is executable Run data that may support detailed feedback.
- `HiddenTestCase` and `HiddenTestSuite` are server-only types. A suite is linked to an exact `ChallengeVersion` ID and is deliberately not a field on `ChallengeVersion`.
- `TestEvaluationResult` and `EvaluationResult` are internal outcomes. A future Submit API must map them to a separate aggregate-only response rather than serialize them directly.

## Model execution

LLM execution and deterministic grading are separate operations. The asynchronous `LLMProvider` port executes one `LLMExecutionRequest`; `EvaluationEngine` grades the returned text later and never calls a provider itself. `RunChallengeUseCase` composes these two steps without importing Groq, FastAPI, or the hidden-test types. A future Submit use case will provide its own server-only orchestration and sanitized response.

`LLMExecutionRequest` keeps the player-authored prompt, test-case input, and immutable challenge `ModelConfiguration` as distinct fields. `GroqProvider` constructs chat messages in this exact order:

1. an optional `system` message containing the challenge-controlled system wrapper;
2. a `user` message containing the player-authored prompt unchanged;
3. a second `user` message containing the test-case input unchanged when it is text, or canonical compact JSON when it is structured.

This ordering is part of evaluation fairness. The adapter sends the configured opaque model ID, temperature, and maximum output tokens exactly; `configuration_version` remains DR. PROMPT metadata and is not sent to Groq. Players cannot select or override these values.

`LLMExecutionResult` exposes only generated text, the model identifier reported by the provider, and optional provider-neutral input/output/total token usage. Raw SDK responses never cross the adapter. These usage values are operational metadata and are not used for prompt-efficiency scoring.

The Groq client uses a configurable request timeout (`GROQ_TIMEOUT_SECONDS`, default 30 seconds) and explicitly disables the SDK's automatic retries. Application retry policy is intentionally deferred. Authentication, rate-limit, timeout, malformed-response, and generic provider failures are translated to project-owned safe errors.

## Graders and scoring

Graders are interchangeable implementations of the generic `Grader` protocol. All six MVP strategies are deterministic and implemented:

- `ExactMatchGrader` performs strict case-sensitive equality without trimming or normalization.
- `CaseInsensitiveExactMatchGrader` applies case folding to text and adds no substring, fuzzy, or whitespace behavior.
- `AllowedLabelGrader` performs strict, case-sensitive membership in the configuration's label set.
- `JsonSchemaGrader` parses model text as JSON and validates it with JSON Schema Draft 2020-12. The small, mature `jsonschema` package is used rather than implementing the standard locally.
- `FieldComparisonGrader` compares only configured top-level fields. Extra fields do not fail a result; missing or different configured fields do.
- `ArrayComparisonGrader` supports the configured ordered or unordered mode. Unordered matching is count-aware, including for duplicate or unhashable JSON values.

`GraderRegistry` is an explicit per-instance resolver. Typed adapters bind each `GraderType` and configuration class to an implementation, reject mismatched configuration, and avoid global mutable state. `with_builtins()` constructs a new registry containing the six standard graders. Adding a future grader requires a configuration, implementation, and registration rather than another branch in the engine.

`EvaluationEngine` evaluates outputs that have already been produced; it does not call an LLM. `evaluate_test` resolves and grades one visible or hidden case. `evaluate_batch` associates outputs by test-case ID, rejects empty suites, duplicate test IDs, and unknown output IDs, and converts a missing known output into a normal `missing_output` failure. Aggregates report passed count, total count, and percentage accuracy (`8 / 10 = 80.0`).

`GradeResult` contains a pass/fail decision plus an optional machine-readable `FailureReason` and deliberately narrow `SafeDiagnostic`. Normal wrong answers, malformed model JSON, schema violations, missing fields, array mismatches, and missing outputs are failed results rather than exceptions. Invalid trusted configuration or malformed batch association is a domain error.

Safe diagnostics provide only a stable code and safe message: they have no generic expected/actual payload fields that could accidentally disclose hidden answers. Internal results likewise contain a test ID and grade but no expected value. Future Run use cases may deliberately combine visible test data with internal results; Submit must map results to a sanitized aggregate DTO. The evaluation engine itself does not impose one shared serialized response shape.

Each `ChallengeVersion` records a provider-neutral `ModelConfiguration`, a default `EvaluationConfiguration`, and a validated `ScoringConfiguration`. Every executable test also carries its effective grader configuration explicitly, allowing future per-case strategies without relying on implicit mutable state.

Scoring will be pure domain logic with challenge-specific configuration. `ScoringConfiguration` records accuracy/efficiency weights, token-based `EfficiencyThresholds`, and `StarThresholds`, but no scoring or star-award algorithm exists yet. The challenge's `prompt_token_limit` is a separate hard admission constraint and is not treated as an efficiency threshold.

Tests for evaluation will use deterministic fake providers. They must never invoke Groq or another external model service.
