# Security

Hidden-test secrecy is a hard architectural requirement, not a presentation concern.

- Hidden test inputs, expected outputs, database rows, and answer-revealing grader configuration exist only on trusted server-side infrastructure.
- API response models for submissions are explicit sanitized DTOs. Internal test/persistence models must never be returned directly.
- Secrets never enter frontend code or bundles. Variables prefixed `NEXT_PUBLIC_` are public by definition.
- LLM API keys, including `GROQ_API_KEY`, are backend-only and are accessed by infrastructure adapters.
- `GROQ_API_KEY` is represented as a validated secret setting and is never copied into provider-neutral requests or responses. Provider construction fails safely when the key is absent.
- Groq SDK exceptions and raw responses do not cross the infrastructure boundary. Client-facing messages use project-owned errors without provider payloads or credentials.
- Provider requests and failures must not be logged indiscriminately. API keys, hidden test inputs, complete player prompts, and raw provider bodies are excluded from default logging.
- The backend does not trust user IDs, roles, scores, or authorization claims supplied in request bodies. Future authentication is validated server-side and identity is taken from that trusted context.
- Future Supabase/PostgreSQL policies must prevent clients from reading hidden-test tables. Service-role credentials remain backend-only, and row-level security is defense in depth rather than a reason to expose sensitive tables.
- Logs, tracing, errors, and analytics must not contain hidden tests or secrets. Provider and evaluation errors returned to clients are sanitized.
- Visible and hidden test repositories should expose different interfaces or safe query paths to reduce accidental mixing.
- The Run use case reads only `ChallengeVersion.visible_test_cases`. Its explicit API response permits visible expected and actual values but has no hidden-suite, raw provider response, SDK exception, or credential field.
- The in-memory playable challenge contains no `HiddenTestSuite`; future Submit orchestration must obtain hidden tests through a separate server-only port.

Run API tests inspect serialized responses for hidden-data and provider-detail fields. Before implementing Submit, add equivalent forbidden-field and repository-boundary authorization tests for its separate sanitized response.
