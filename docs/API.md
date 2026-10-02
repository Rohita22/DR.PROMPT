# API

All public endpoints are versioned under `/api/v1`. Breaking contract changes require a new major path; compatible additions remain in the current version. FastAPI exposes local interactive OpenAPI documentation at `/docs` and the machine-readable schema at `/openapi.json`.

## `GET /api/v1/health`

Reports whether the API process can serve requests. It does not currently check external dependencies.

Response `200 OK`:

```json
{
  "status": "ok",
  "service": "dr-prompt-api"
}
```

## `GET /api/v1/challenges`

Returns safe ordered challenge-map metadata. Authentication is optional. Anonymous callers see the first published challenge as `available` and later challenges as `locked`; a valid bearer token adds current-user progress and derived statuses.

```json
{
  "challenges": [
    {
      "id": "control-exact-output",
      "slug": "exact-output",
      "title": "Exact Output",
      "track": "control",
      "challenge_type": "text",
      "difficulty": "easy",
      "order": 1,
      "status": "available",
      "best_score": null,
      "best_stars": 0,
      "attempts": 0,
      "completed": false
    }
  ]
}
```

`challenge_type` is `text` or `application` (additive field). Statuses are `locked`, `available`, `completed`, and `mastered`. Completed and mastered challenges remain accessible. No executable tests, hidden data, grader configuration, or model configuration is included.

## `GET /api/v1/challenges/{challenge_slug}`

Returns safe playable content for an accessible challenge: title, objective, constraints, explanatory examples, prompt limit, current progress, `challenge_type`, and `application`. `application` is `null` for TEXT; for APPLICATION it is `{"editable_files": [...], "starter_preview_viewports": ["desktop", "mobile"]}`. The build command, limits, and check IDs are never included. It returns no executable or hidden tests. Anonymous users may retrieve only the first challenge. A locked anonymous request returns `401 challenge_authentication_required`; a locked authenticated request returns `403 challenge_locked`.

## `GET /api/v1/challenges/{challenge_slug}/starter-preview/{viewport}.png`

Returns the committed starter screenshot (`image/png`) of a published APPLICATION challenge for a configured public screenshot viewport. The unmodified starter is public reference material, so this route is not progression-gated. Unknown challenges, TEXT challenges, and unknown viewports return `404`.

## `GET /api/v1/challenges/{challenge_slug}/leaderboard`

Returns the public leaderboard for the challenge's current published version and exact configured model environment. Authentication is optional. `limit` defaults to 25 and must be between 1 and 100; `offset` defaults to 0.

```json
{
  "challenge": "exact-output",
  "version": "1",
  "entries": [
    {
      "rank": 1,
      "player": "aiwizard",
      "score": 98.4,
      "accuracy": 100.0,
      "prompt_tokens": 52,
      "stars": 3,
      "submitted_at": "2026-01-01T00:00:00Z",
      "is_current_user": false
    }
  ],
  "current_user_entry": null,
  "total_entries": 1,
  "limit": 25,
  "offset": 0,
  "has_more": false
}
```

Only the best qualifying submission per user appears. Selection and ranking use final score descending, accuracy descending, prompt tokens ascending, submission time ascending, and submission UUID as a deterministic final safeguard. Positions are unique and sequential. Historical challenge versions and incompatible model configurations are excluded without being deleted.

With a valid optional bearer token, `current_user_entry` contains the verified user's position even when it is outside the requested page. Anonymous requests return `null`. Nullable usernames use a privacy-safe `Player-XXXX` fallback. The response cannot represent email, auth identity, local user ID, prompt content, hidden tests or outputs, provider metadata, or XP ledger data.

## `POST /api/v1/challenges/{challenge_slug}/run`

Runs the player's prompt independently against every visible test in an accessible published challenge version, then grades the returned model text with the deterministic evaluation engine. The prototype exposes five ordered CONTROL challenges.

Run accepts optional bearer authentication. Anonymous users may run the first challenge; later challenges require authenticated progression. Locked requests fail before provider execution.

Request:

```json
{
  "prompt": "Return exactly YES when the service is available; otherwise return exactly NO."
}
```

Response `200 OK`:

```json
{
  "challenge": "exact-output",
  "challenge_id": "control-exact-output",
  "version": "1",
  "passed": 2,
  "total": 3,
  "accuracy": 66.67,
  "tests": [
    {
      "id": "visible-1",
      "input": "The status page says all systems are operational.",
      "expected": "YES",
      "actual": "YES",
      "passed": true,
      "failure_reason": null
    }
  ]
}
```

Run feedback intentionally includes visible inputs, expected outputs, and actual outputs so players can diagnose their prompts. This response type is not suitable for the future Submit flow and contains no hidden-test data, raw provider response, or provider metadata.

The first implementation executes visible tests sequentially and fails fast if any provider call fails. Provider failures are infrastructure failures, not incorrect player answers: safe project-owned errors are returned as `502`, rate limits as `429`, and timeouts as `504`. An unknown or unpublished challenge returns `404`; request validation failures return `422`.

Run does not currently enforce the Submit hard token limit. Character count is deliberately not used as a token-count substitute.

## `POST /api/v1/challenges/{challenge_slug}/submit`

Executes the player's prompt independently against the selected challenge version's server-only hidden test suite and returns sanitized aggregate accuracy.

Requires `Authorization: Bearer <supabase-access-token>`. The backend verifies the token and derives submission ownership; the body cannot contain a user ID.

Submit also enforces ordered challenge access before token counting, hidden-suite loading, model execution, or persistence. A locked challenge returns `403 challenge_locked` and produces no calls, submissions, progress, or XP.

Request:

```json
{
  "prompt": "Return exactly YES when the service is available; otherwise return exactly NO."
}
```

Response `200 OK`:

```json
{
  "challenge": "exact-output",
  "version": "1",
  "passed": 5,
  "total": 6,
  "accuracy": 83.33,
  "prompt_tokens": 42,
  "efficiency": 100.0,
  "score": 86.67,
  "stars": 1,
  "xp_earned": 100,
  "total_xp": 100,
  "best_score": 86.67,
  "best_stars": 1,
  "completed": true
}
```

Unlike Run, Submit never returns a test array. Its response schema has no fields for hidden identifiers, inputs, expected outputs, actual outputs, grader configuration, diagnostics, or provider metadata. The hidden suite is retrieved separately on the server and must match the exact published challenge version. Scoring fields reveal only the player-authored prompt token count and challenge-configured aggregate calculations.

Hidden cases execute sequentially and fail fast on provider errors. Provider failures use the same safe `429`, `502`, and `504` semantics as Run and never become failed answers or partial accuracy. Missing or inconsistent hidden evaluation configuration returns `503` with the safe `hidden_evaluation_unavailable` error. A completed score is returned only after its authoritative submission record commits; database failures return sanitized `503 persistence_error`. Unknown challenges return `404`, and invalid request bodies return `422`.

Missing or invalid bearer authentication returns `401` with `WWW-Authenticate: Bearer`. Authentication/JWKS infrastructure failure returns a sanitized `503`; raw tokens, claims, signing metadata, and cryptographic errors are never returned.

Submit counts the player-authored prompt locally with the configured model's authoritative tokenizer before accessing hidden tests. A prompt over the challenge's 300-token hard limit returns `422` with code `prompt_too_long`, including safe actual and maximum counts, performs no model calls, and persists nothing. Efficiency, weighted score, and stars use the versioned challenge configuration.

After successful evaluation, submission persistence, progress update, and XP awards commit atomically. `xp_earned` is newly awarded by this attempt and may be zero. `total_xp` is derived from the user's ledger. Best score follows final score with ties preserving the earlier best submission; best stars are independent and monotonic. No request field can supply or override these values.

### APPLICATION Run and Submit

The same `/run` and `/submit` endpoints return an APPLICATION-specific shape for APPLICATION challenges; TEXT responses are unchanged. APPLICATION responses carry `"challenge_type": "application"` and use `evaluation_score` (passed checks / total checks × 100) instead of `accuracy`. The frontend should send the bearer token on Run: Responsive Hero is progression-gated, like every non-first challenge.

Run `200 OK`:

```json
{
  "challenge_type": "application",
  "challenge": "responsive-hero",
  "challenge_id": "control-responsive-hero",
  "version": "1",
  "passed": 3,
  "total": 4,
  "evaluation_score": 75.0,
  "agent": { "status": "applied", "message": null },
  "changed_files": [{ "path": "src/styles.css", "additions": 21, "deletions": 0 }],
  "build": { "status": "passed", "log": "Built dist/index.html and dist/styles.css." },
  "checks": [
    { "id": "build", "label": "Project builds", "passed": true, "message": null },
    { "id": "mobile_no_overflow", "label": "No horizontal overflow at 390px", "passed": false,
      "message": "At 390px the page scrolls horizontally." }
  ],
  "screenshots": [
    { "viewport": "desktop", "width": 1280, "height": 800, "image": "data:image/png;base64,..." },
    { "viewport": "mobile", "width": 390, "height": 844, "image": "data:image/png;base64,..." }
  ]
}
```

`agent.status` is `rejected`, with a safe message, when the agent's edits fail validation. The build is then `skipped`, there are no screenshots, and every check fails. `build.status` is `passed`, `failed`, or `skipped`; logs are sanitized and truncated. Only visible checks appear.

Submit `200 OK`:

```json
{
  "challenge_type": "application",
  "challenge": "responsive-hero",
  "version": "1",
  "passed": 9,
  "total": 9,
  "evaluation_score": 100.0,
  "prompt_tokens": 64,
  "efficiency": 100.0,
  "score": 100.0,
  "stars": 3,
  "xp_earned": 175,
  "total_xp": 1240,
  "best_score": 100.0,
  "best_stars": 3,
  "completed": true,
  "agent_status": "applied",
  "screenshot": { "viewport": "desktop", "width": 1280, "height": 800, "image": "data:image/png;base64,..." }
}
```

Submit has no field for check IDs, labels, messages, build logs, or changed files. The hard prompt limit is 400 tokens for this challenge.

APPLICATION Run and Submit use the verified local user for server-authoritative resource controls. Run defaults to a 10-second per-user cooldown; Submit defaults to 20 seconds. A local cooldown returns `429 application_rate_limited` and an integer `Retry-After` header. A second Run or Submit while either APPLICATION operation is active for that user returns `409 application_execution_in_progress`. Upstream model throttling remains the distinct `429 llm_rate_limit_error` code.

APPLICATION Submit requires an opaque `Idempotency-Key` header (8–255 visible non-whitespace characters). Its scope is the authenticated user, exact challenge version, and Submit operation. A completed duplicate returns the same authoritative result without a model call or additional submission/progression/XP effects. A duplicate still executing returns the in-progress conflict. Infrastructure failures persist no authoritative result and release the key for retry; because execution started, its local Submit cooldown still applies. TEXT Submit accepts the same endpoint without this header and is unchanged.

Errors:

- a coding-agent timeout returns `504 llm_timeout_error`;
- a detected model refusal returns `502 agent_refused`;
- an incomplete length-truncated response returns `502 output_truncated`;
- a provider response that violates the requested structured contract returns `502 agent_invalid_response`;
- provider failures keep their existing `429`, `502`, and `504` mappings;
- a build timeout, missing toolchain, or unavailable browser returns `503 application_environment_unavailable`;
- an IMAGE challenge would return `503 unsupported_challenge_type`.

None of these persist anything.

Expected application/domain failures will use a consistent shape:

```json
{
  "error": {
    "code": "machine_readable_code",
    "message": "Safe human-readable message"
  }
}
```

As endpoints grow, use the OpenAPI specification to generate frontend types or a small client rather than maintaining duplicate schemas by hand.

## Admin challenge authoring

All admin routes require `X-Admin-Key`. Missing or incorrect credentials return `401`; an unconfigured server returns `503`. The key is never accepted in request bodies or returned in responses.

- `GET /api/v1/admin/challenges` lists stable challenge metadata, selected authoring/current version state, and visible/hidden test counts.
- `GET /api/v1/admin/challenges/{slug}` returns complete protected authoring data, including hidden tests and version history.
- `POST /api/v1/admin/challenges` creates version 1. `publication_state: "draft"` is used by the builder; the default `"published"` preserves the original endpoint's create-and-publish contract.
- `PUT /api/v1/admin/challenges/{slug}` saves only the selected draft. Published and retired versions reject mutation.
- `POST /api/v1/admin/challenges/{slug}/versions` clones the latest authored/published definition into the next numeric draft version.
- `POST /api/v1/admin/challenges/{slug}/test` accepts `{ "prompt": "..." }`, independently executes visible and hidden cases, and returns detailed authoring diagnostics plus aggregate scoring. It creates no submission, progress, XP, unlock, or leaderboard state.
- `POST /api/v1/admin/challenges/{slug}/publish` accepts an optional version and atomically makes that complete draft active while retiring the previous published version.
- `POST /api/v1/admin/challenges/{slug}/unpublish` removes the challenge from public playable reads without deleting any version or player history.

Test-case authoring uses a discriminator-bearing `grader` object. Supported `type` values are `exact_match`, `case_insensitive_exact_match`, `allowed_label`, `json_schema`, `field_comparison`, and `array_comparison`; each accepts only its typed settings. Public challenge endpoints remain unchanged and never return hidden authoring data.

## `GET /api/v1/me`

Requires the same bearer authentication as Submit. It verifies/synchronizes the local user and returns only safe application identity:

```json
{
  "id": "local-user-uuid",
  "email": "player@example.com",
  "username": null
}
```

The response excludes external provider subject IDs, tokens, raw claims, provider sessions, and signing metadata.

## `GET /api/v1/me/progress`

Requires bearer authentication and returns progress only for the verified current user:

```json
{
  "total_xp": 175,
  "challenges_completed": 1,
  "stars_earned": 3,
  "challenges": [
    {
      "challenge": "exact-output",
      "best_score": 100.0,
      "best_stars": 3,
      "attempts": 4,
      "completed": true,
      "completed_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

The endpoint contains no XP ledger IDs, submission prompts, provider identity, or other users' progress. Missing or invalid authentication returns `401` with `WWW-Authenticate: Bearer`.

## `GET /api/v1/me/profile`

Requires bearer authentication and returns a high-level game profile only for the verified current user. Level boundaries are server-provided so clients do not duplicate the configurable 500-XP level rule.

```json
{
  "player": "Player-A1B2",
  "level": 2,
  "level_progress": {
    "level_floor": 500,
    "next_level_at": 1000,
    "earned_in_level": 340,
    "required_in_level": 500
  },
  "total_xp": 840,
  "challenges": { "completed": 4, "total": 5 },
  "stars": { "earned": 10, "total": 15 },
  "three_star_completions": 2,
  "best_leaderboard_position": 7,
  "recent_activity": [
    {
      "challenge": "formatting-rules",
      "title": "Formatting Rules",
      "score": 94.5,
      "accuracy": 100.0,
      "stars": 2,
      "prompt_tokens": 81,
      "xp_earned": 25,
      "submitted_at": "2026-01-02T10:00:00Z"
    }
  ]
}
```

XP is ledger-derived, challenge and star totals include currently published playable challenges, and best rank uses the same active-version/model eligibility and deterministic ordering as challenge leaderboards. Recent activity contains at most five newest authoritative submissions. It never includes email, user UUID, provider identity, prompt content, hidden evaluation data, raw model output, model metadata, or XP ledger records.

## Application Platform v1 admin schemas

`GET /api/v1/admin/application-packages` returns the two registered package IDs, display names, descriptions, safe authoring defaults, and visible/private check metadata (implementation ID, viewport IDs, count, minimum width ratio, tolerance). `GET /api/v1/admin/application-packages/{package_id}/preview/{viewport}.png` serves protected package previews. Both use the same admin authorization as all builder routes; no evaluator source or absolute paths are returned.

Create/update accept `challenge_type: "text" | "application"` (omitted means TEXT for compatibility). APPLICATION requires an `application` object with `package_id`, `editable_files`, `visible_checks`, `hidden_checks`, `viewports`, and `limits`; text cases/examples must be empty. The application object forbids extra fields. Each viewport has `id`, `width`, `height`, `label`, `screenshot`; measurement sizes must match the package, and screenshot selection cannot expose private views. Limits include agent/build/browser timeouts, maximum file bytes/count, and log characters, bounded by the package. Build argv and evaluator parameters cannot be supplied. TEXT rejects application configuration; IMAGE is rejected. Model settings additionally preserve optional `reasoning_effort`.

Admin detail returns `challenge_type` and the typed `application` object. Existing version/create/publish/unpublish routes apply to both types. Type cannot change after creation. APPLICATION Test returns `application` (visible checks, screenshots, build, changes) and admin-only `hidden_checks`, alongside common score fields. It evaluates the union with one agent call and creates no gameplay state. TEXT Test retains its existing visible/hidden test arrays.

Public screenshot artifacts add `label`; the UI uses labels and dimensions dynamically. Public detail still exposes only editable files and safe starter viewport IDs. Public Submit remains aggregate-only with a single safe screenshot; screenshot labels are display metadata, not hidden check labels. See [APPLICATION_PLATFORM.md](APPLICATION_PLATFORM.md) for the persisted configuration and exact package policy.
