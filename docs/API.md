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
