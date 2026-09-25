# Security

Hidden-test secrecy is a hard architectural requirement, not a presentation concern.

- Hidden test inputs, expected outputs, database rows, and answer-revealing grader configuration exist only on trusted server-side infrastructure.
- `SubmitChallengeResult` and `SubmitChallengeResponse` are explicit aggregate-only DTOs. Their scoring additions contain only player prompt token count and aggregate calculations. Neither type can represent a hidden test record; internal evaluation and storage models are never returned directly.
- Secrets never enter frontend code or bundles. Variables prefixed `NEXT_PUBLIC_` are public by definition.
- LLM API keys, including `GROQ_API_KEY`, are backend-only and are accessed by infrastructure adapters.
- `GROQ_API_KEY` is represented as a validated secret setting and is never copied into provider-neutral requests or responses. Provider construction fails safely when the key is absent.
- Groq SDK exceptions and raw responses do not cross the infrastructure boundary. Client-facing messages use project-owned errors without provider payloads or credentials.
- Provider requests and failures must not be logged indiscriminately. API keys, hidden test inputs, complete player prompts, and raw provider bodies are excluded from default logging.
- The backend does not trust user IDs, roles, scores, or authorization claims supplied in request bodies. Submit request schemas reject extra fields, and ownership comes exclusively from a cryptographically verified bearer token mapped to a local user.
- XP, stars, completion, attempts, and best results are server-authoritative. The Submit body accepts only the player prompt; progression values are derived from the completed hidden evaluation and cannot be supplied by the browser.
- Challenge availability is server-authoritative and derived for the verified local user. Detail, Run, and Submit reject locked challenges; manually changing a slug or frontend state cannot bypass the check. Anonymous access is limited to the first published challenge in a track.
- Visible and hidden executable cases are separate PostgreSQL tables. Only the server-side hidden-suite repository queries `hidden_test_cases`; the public challenge repository has no hidden-data query or return type.
- `DATABASE_URL` is a backend-only secret. Database driver errors, SQL text, and connection details are translated to the safe `persistence_error` boundary before an API response.
- Future Supabase RLS policies must deny browser roles access to hidden-test and authoritative submission tables. The browser does not connect directly to evaluation tables; RLS remains defense in depth rather than the primary secrecy boundary.
- Logs, tracing, errors, and analytics must not contain hidden tests or secrets. Provider and evaluation errors returned to clients are sanitized.
- Visible and hidden test storage use separate ports and adapters. `ChallengeReader` returns only `PlayableChallenge`; the server-only `HiddenTestSuiteReader` is wired exclusively into Submit.
- The Run use case reads only `ChallengeVersion.visible_test_cases`. Its explicit API response permits visible expected and actual values but has no hidden-suite, raw provider response, SDK exception, or credential field.
- The playable challenge contains no `HiddenTestSuite`. Submit retrieves the suite separately by exact challenge and version identity and verifies the returned version before executing it.
- Prompt counting is local and operates only on the player-authored prompt. It does not send content to a tokenizer service or expose provider usage, system wrappers, or hidden test inputs.

Run and Submit tests assert their deliberately different response schemas. Submit's schema is restricted to safe aggregate and scoring fields, with no optional detail escape hatch. Missing or mismatched hidden evaluation configuration returns a safe availability error without suite data. Completed submissions persist no hidden inputs, expected values, or model outputs; they refer to the exact versioned evaluation environment instead.

## Authentication and tokens

- Supabase Auth owns OAuth credentials and sessions; DR. PROMPT stores only a provider identity reference and safe profile metadata.
- FastAPI verifies asymmetric access-token signatures with the project's public JWKS. It also requires an allowed algorithm, expiration, issuer, audience, and non-blank subject.
- The JWKS is cached in process for ten minutes. Unknown key IDs force one refresh. Network or malformed-JWKS failures fail closed with a sanitized service error.
- Missing, malformed, expired, incorrectly signed, or otherwise invalid tokens return `401` with `WWW-Authenticate: Bearer`. Tokens and cryptographic exception details are never returned or logged.
- The stable external identity is `(supabase, sub)`, never email. Email changes synchronize safe metadata without changing ownership.
- The local users uniqueness constraint protects concurrent first access. Existing pre-auth development submissions may remain ownerless; new Submit use-case records always contain the verified local user ID.
- XP milestone uniqueness is enforced by `(user_id, challenge_id, reason)`, and one progress row is enforced per `(user_id, challenge_id)`. The authenticated `/me/progress` query is always scoped to the verified local UUID.
- The frontend contains only `NEXT_PUBLIC_SUPABASE_URL` and the publishable Supabase key. Service-role/secret keys, `DATABASE_URL`, and `GROQ_API_KEY` must never enter browser environment variables or bundles.
- The backend needs `SUPABASE_URL` for issuer/JWKS derivation but no Supabase service-role key and no Supabase SDK.
