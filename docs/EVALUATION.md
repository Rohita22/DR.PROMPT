# Evaluation

Evaluation implements the Run → Submit loop while enforcing a strict trust boundary.

Evaluation is challenge-family-specific. TEXT and static APPLICATION are implemented. The initial sections describe deterministic text grading; application evaluation is described below and in [APPLICATION_PLATFORM.md](APPLICATION_PLATFORM.md). IMAGE remains deferred.

## Run

`RUN` is implemented as an application use case. `RunChallengeUseCase` retrieves a published `PlayableChallenge` through the minimal `ChallengeReader` port and delegates execution to `TextChallengeExecutor.execute_visible`. The executor runs each `VisibleTestCase` independently through `LLMProvider`, associates generated text by test ID, and delegates all grading and aggregation to `EvaluationEngine`.

Before execution, Run applies the same derived challenge-access policy as detail and Submit. Anonymous players may run the first CONTROL challenge. Later challenges require authentication and completion of the preceding challenge; locked requests make no provider calls.

The three prototype tests execute sequentially for deterministic, easy-to-debug behavior. If a provider call fails, Run stops and propagates the project-owned provider error; infrastructure failure is never converted into a wrong player answer. Because visible examples are already public, the purpose-built Run response includes test inputs, model outputs, expected outputs, and stable failure reasons. This mode supports iteration and is not an authoritative score.

The initial in-memory challenge records a prompt hard limit, but the use case does not enforce it until an authoritative tokenizer is available. Character length is not treated as token count.

## Submit

`SUBMIT` is implemented as a separate application use case. `SubmitChallengeUseCase` retrieves the same published challenge through `ChallengeReader`. `TextChallengeExecutor.execute_hidden` then requests a server-only `HiddenTestSuite` through `HiddenTestSuiteReader` using the exact `ChallengeVersion` ID. It rejects a missing suite or a suite whose version does not match before model execution begins.

Each CONTROL challenge has six deterministic hidden cases. Each case is executed independently and sequentially through `LLMProvider`, then the existing `EvaluationEngine` grades outputs associated by test ID. Provider failures stop the submission and propagate as project-owned execution errors; they are not converted into failed tests or partial accuracy. Submit checks access before token counting, hidden-suite loading, or provider execution.

The browser receives only `SubmitChallengeResult` mapped to `SubmitChallengeResponse`: challenge slug, version, passed count, total count, accuracy, player prompt tokens, efficiency, final score, and stars. These types contain no per-test collection or fields for hidden IDs, inputs, expected outputs, actual outputs, grader configuration, or provider metadata. Detailed `EvaluationResult` data remains internal.

The intended flow is:

```text
Browser → FastAPI → Submit use case → LLMProvider
                                  ↘ server-only hidden-suite reader
                    grader → aggregate sanitizer → Browser
```

DTOs for public challenge data, visible run results, internal evaluation data, and submitted results must be distinct. Do not reuse an internal persistence model as an API response. This makes accidental hidden-test serialization difficult.

The implemented domain makes the distinction explicit:

- `VisibleExample` is explanatory challenge content and is never implicitly executable.
- `VisibleTestCase` is executable Run data that may support detailed feedback.
- `HiddenTestCase` and `HiddenTestSuite` are server-only types. A suite is linked to an exact `ChallengeVersion` ID and is deliberately not a field on `ChallengeVersion`.
- `TestEvaluationResult` and `EvaluationResult` are internal outcomes. Submit maps their aggregates to a separate result and response rather than serializing them directly.

## Model execution

LLM execution and deterministic grading are separate operations. The asynchronous `LLMProvider` port executes one `LLMExecutionRequest`; `EvaluationEngine` grades the returned text later and never calls a provider itself.

`TextChallengeExecutor` (in `app/domains/execution`) is the only component that composes the two for players. `RunChallengeUseCase` and `SubmitChallengeUseCase` resolve it from the challenge version's `ChallengeType` through `ChallengeExecutorResolver`, then call `execute_visible` (visible tests) or `execute_hidden` (the server-only suite, loaded and version-checked inside the executor). The executor returns an internal `ChallengeExecutionResult`:

- `evaluation_score` equals `EvaluationResult.accuracy` for TEXT;
- `passed_checks` and `total_checks`;
- per-test `check_results` (grades with failure reasons);
- `TextOutputArtifact`s holding the generated text for each test ID.

Run maps these into detailed visible feedback. Submit feeds `evaluation_score` into `ScoringService` as `accuracy` and keeps only aggregates. The executor does no token counting, scoring, persistence, or progression. A challenge type with no registered executor fails with `UnsupportedChallengeTypeError` before any model call. None of these components import Groq or FastAPI.

`LLMExecutionRequest` keeps the player-authored prompt, test-case input, immutable challenge `ModelConfiguration`, and an optional provider-neutral structured-output specification as distinct fields. `GroqProvider` constructs chat messages in this exact order:

1. an optional `system` message containing the challenge-controlled system wrapper;
2. a `user` message containing the player-authored prompt unchanged;
3. a second `user` message containing the test-case input unchanged when it is text, or canonical compact JSON when it is structured.

This ordering is part of evaluation fairness. The adapter sends the configured opaque model ID, temperature, maximum output tokens, and optional reasoning effort exactly; `configuration_version` remains DR. PROMPT metadata and is not sent to Groq. Players cannot select or override these values. TEXT requests do not ask for structured output and preserve their existing behavior. Responsive Hero adds a strict JSON Schema for exactly the existing whole-file edit envelope and uses hidden reasoning output, so commentary or reasoning cannot contaminate the edit payload.

`LLMExecutionResult` exposes only generated text, the model identifier reported by the provider, and optional provider-neutral input/output/total token usage. Raw SDK responses never cross the adapter. These usage values are operational metadata and are not used for prompt-efficiency scoring.

The Groq client uses a configurable request timeout (`GROQ_TIMEOUT_SECONDS`, default 30 seconds) and explicitly disables the SDK's automatic retries. There is no application retry loop. Authentication, rate-limit, timeout, refusal, output-truncation, malformed-response, and generic provider failures are translated to project-owned safe errors.

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

Scoring is pure domain logic with challenge-specific configuration. `ScoringConfiguration` records accuracy/efficiency weights, token-based `EfficiencyThresholds`, and `StarThresholds`. The challenge's `prompt_token_limit` is a separate hard admission constraint and is not treated as an efficiency threshold.

## Token counting and scoring

Submit performs scoring in this exact order:

1. load the published challenge version;
2. count only the player's authored prompt with the model-compatible local tokenizer;
3. reject the request before hidden-suite loading or model execution if the prompt exceeds the hard limit;
4. load and verify the exact hidden suite;
5. execute and deterministically grade the hidden cases;
6. use aggregate accuracy plus prompt token count and the challenge's scoring configuration to calculate efficiency, final score, and stars;
7. atomically persist the owned submission, update challenge progress, and append newly earned XP milestones;
8. map scoring and safe progression aggregates to the sanitized response.

Persistence happens only after complete evaluation and scoring. Provider failures and prompt validation failures save nothing. Submission, progress, and XP changes commit in one transaction; a failure prevents a success response. Submission rows store reproducibility metadata and aggregate scores, but not hidden inputs, expected outputs, or actual model outputs. Attempts count completed authoritative evaluations, including zero-star results. Completion is set once when stars first reach one; best score and its submission are score-driven, while best stars are tracked independently and never decrease.

`PromptTokenCounter` is a provider-neutral port. The current adapter uses OpenAI's authoritative `o200k_harmony` ordinary-text encoding for `openai/gpt-oss-20b`, backed by a local, SHA-256-verified copy of the official vocabulary. It performs no network request during counting. Provider usage is deliberately ignored because it includes system and test-input tokens.

`EfficiencyThresholds` is an ordered set of inclusive token ceilings. The prototype challenge uses `≤60 → 100`, `≤100 → 90`, `≤150 → 75`, `≤250 → 60`, and `>250 → 40`. Its separate prompt hard limit is 300 tokens.

`ScoringService` calculates `accuracy × accuracy_weight + efficiency × efficiency_weight`. The final score uses decimal arithmetic and rounds once to two decimal places with round-half-up semantics. Accuracy and efficiency remain on a 0–100 scale.

Stars are accuracy-gated and challenge-specific: zero below the one-star threshold, one at the one-star threshold, two at the two-star threshold, and three only at the three-star accuracy threshold when the optional three-star prompt-token ceiling is also met. The prototype uses 70, 90, and 100 percent accuracy, with at most 60 player-prompt tokens required for three stars.

Tests for evaluation will use deterministic fake providers. They must never invoke Groq or another external model service.

## Evaluation for other families

### Shared principles

- **Programmatic first.** Builds, tests, browser checks, and explicit requirement checks are preferred. An LLM-as-judge is not a primary evaluator.
- **Show the AI's result.** Run exposes the actual output or artifact the player's prompt produced, not only a score.
- **Two evaluation modes stay distinct.** Run evaluates visible checks and may return detailed debugging data. Submit evaluates hidden checks and returns only aggregates and artifacts that do not compromise hidden evaluation.
- **Normalized output.** Each family produces `ChallengeExecutionResult.evaluation_score` (0–100). Scoring combines it with prompt-token efficiency and feeds stars, XP, progression, and leaderboards unchanged.
- **Infrastructure failures are not player failures.** Timeouts, a missing toolchain, or an unavailable browser are never scored as wrong answers.

### Application evaluation — Platform v1

Both packages are evaluated after the coding agent's validated edits are written to a disposable starter copy:

1. **Edit validation.** A malformed response, a path outside the allowlist, a duplicate, an oversized file, too many files, or no actual change rejects the whole edit set. The attempt is then a scored failure: every check fails with `agent_output_rejected` and nothing is built.
2. **Build.** `node build.mjs` runs with a fixed argument list, a 20-second timeout, and a minimal environment. A non-zero exit fails the `build` check and all layout checks; its log is sanitized and returned on Run. A build timeout is an infrastructure error.
3. **Measurement.** Headless Chromium loads `dist/index.html` with JavaScript disabled and only files inside `dist/` reachable. At 1280×800, 1440×900, 390×844, and 320×640 it records the selector-indexed bounding boxes and computed appearance of package-declared elements, horizontal scroll width, CTA hit-testing, and heading structure. Desktop and phone screenshots are captured.
4. **Checks.** The trusted per-instance `ApplicationCheckRegistry` decides pass/fail from typed facts. The following table documents Hero’s preserved check presets:

| Check | Run | Submit | Passes when |
| --- | :-: | :-: | --- |
| `build` | ✓ | | the build exits 0 and produces the page |
| `desktop_two_column` | ✓ | ✓ | at 1280px, content and visual are visible, side by side with content left, share a row, and are each at least 25% of the width |
| `cta_visible` | ✓ | | the CTA is visible at 1280px within the first viewport, and visible at 390px |
| `mobile_no_overflow` | ✓ | ✓ | no horizontal scroll at 390px |
| `wide_two_column` | | ✓ | the same two-column rule at 1440px |
| `small_no_overflow` | | ✓ | no horizontal scroll at 320px |
| `mobile_stacked` | | ✓ | at 390px, content and visual stack vertically and content is at least 60% of the width |
| `cta_interactive` | | ✓ | the CTA is an `a[href]` or a `button`, and it is the topmost element at its centre on desktop and phone |
| `semantic_structure` | | ✓ | the hero is inside `main`, contains exactly one `h1` (the only one on the page), and the CTA is an `a` or `button` |
| `landmarks_unchanged` | | ✓ | the header and footer markup are unchanged apart from whitespace |
| `protected_files_unchanged` | | ✓ | the only files that differ from the starter are allowlisted |

5. **Score.** `evaluation_score = passed / total × 100`, with no weighting. Run uses the 4 visible checks. Submit uses the 9 hidden checks, which re-test the core requirements more strictly alongside hidden-only checks. An unchanged starter passes 5 of 9 on Submit (55.6), which is below the one-star threshold of 70.

Scoring then reuses `ScoringService` with `evaluation_score` in accuracy's role: `0.8 × evaluation + 0.2 × efficiency`. Stars need evaluation scores of 70 / 85 / 100, and three stars also need at most 150 prompt tokens. Token efficiency still counts only the player's prompt. The persisted submission stores `evaluation_score` in the existing `accuracy` column, with checks as passed/total tests (see [DATABASE.md](DATABASE.md)).

**Visibility.** Run returns visible check IDs, labels, and failure messages, the sanitized build log, a changed-file line summary, and desktop and phone screenshots. Submit returns only aggregates, the agent status, and the desktop screenshot of the player's own result. No hidden check ID, label, message, or hidden-viewport measurement is representable in its response.

### Image challenges — later phase

A generated image would be compared with a hidden-configuration target on dimensions such as overall visual similarity, subject, composition, style, and semantic similarity. Nondeterminism, seed control, scoring quality, and model-version comparability must be solved before image scores can be fair enough for leaderboards.

Pricing Grid has four visible checks and fifteen hidden checks covering responsive card layout, objective Pro prominence, preserved names/prices/features/actions, and protected structure. Check presets and their typed parameters are defined in each repository manifest; see [the complete check breakdown](APPLICATION_PLATFORM.md#shipped-content). No subjective AI judge or admin-supplied evaluator code exists. Admin Test evaluates the visible/hidden union over a single generated result; its score describes that union, while Submit remains hidden-suite-only.
