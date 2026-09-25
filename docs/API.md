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

## `POST /api/v1/challenges/{challenge_slug}/run`

Runs the player's prompt independently against every visible test in the published challenge version, then grades the returned model text with the deterministic evaluation engine. The prototype currently exposes one challenge at `exact-output`.

Run is public and does not require authentication.

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

The challenge records a prompt token limit, but Run does not enforce it yet because no authoritative tokenizer has been introduced. Character count is deliberately not used as a token-count substitute.

## `POST /api/v1/challenges/{challenge_slug}/submit`

Executes the player's prompt independently against the selected challenge version's server-only hidden test suite and returns sanitized aggregate accuracy.

Requires `Authorization: Bearer <supabase-access-token>`. The backend verifies the token and derives submission ownership; the body cannot contain a user ID.

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
