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
- Visible and hidden test storage use separate ports and adapters. `ChallengeReader` returns only `PlayableChallenge`. The server-only `HiddenTestSuiteReader` is held by `TextChallengeExecutor` and read only by `execute_hidden`, which only Submit calls. Run calls `execute_visible`, and tests assert that it never reads the hidden suite.
- `ChallengeExecutionResult` is internal and can describe hidden checks; no API schema can represent it. Submit maps only its aggregates.
- The Run use case reads only `ChallengeVersion.visible_test_cases`. Its explicit API response permits visible expected and actual values but has no hidden-suite, raw provider response, SDK exception, or credential field.
- The playable challenge contains no `HiddenTestSuite`. Submit retrieves the suite separately by exact challenge and version identity and verifies the returned version before executing it.
- Prompt counting is local and operates only on the player-authored prompt. It does not send content to a tokenizer service or expose provider usage, system wrappers, or hidden test inputs.
- Leaderboard responses expose only rank, privacy-safe player label, aggregate score, accuracy, prompt-token count, stars, and submission time. They never include email, provider subject, local user UUID, player prompt, hidden evaluation data, model/provider metadata, or XP ledger data.
- Nullable usernames fall back to `Player-XXXX`, derived from a one-way SHA-256 digest of the application user ID. Optional authentication is used only to mark or separately return the verified current user's position; request parameters cannot select another user.
- The authenticated profile is scoped exclusively by the verified local user. It exposes only the privacy-safe player label, derived aggregates, level boundaries, best rank, and sanitized recent submission metrics. It cannot represent email, raw UUIDs, prompts, hidden data, provider/model metadata, or individual XP ledger records.

Run and Submit tests assert their deliberately different response schemas. Submit's schema is restricted to safe aggregate and scoring fields, with no optional detail escape hatch. Missing or mismatched hidden evaluation configuration returns a safe availability error without suite data. Completed submissions persist no hidden inputs, expected values, or model outputs; they refer to the exact versioned evaluation environment instead.

## Application challenge execution — Platform v1

These controls protect both Responsive Hero and Pricing Grid. Each is covered by tests in `tests/infrastructure/test_application_isolation.py`, `tests/domains/test_application_domain.py`, and `tests/domains/test_application_executor.py`.

- **Disposable workspaces.** Every Run and Submit copies the canonical starter into a new `tempfile.mkdtemp` directory and deletes it in a `finally` block, including on errors and timeouts. The canonical starter under `backend/application_challenges/` is never written. Only starter files are copied: no `.env`, backend source, or repository files.
- **No shell, no player-controlled commands.** The build is a fixed argument list from the versioned challenge configuration (`["node", "build.mjs"]`). It runs with `subprocess.run(..., shell=False)`, stdin closed, and a timeout. The player prompt only ever reaches the model and never becomes a command, argument, path, or environment value.
- **Minimal environment.** The build process receives only `PATH` (the Node directory), `NO_COLOR`, and `SYSTEMROOT`. The browser receives only `SYSTEMROOT`. `GROQ_API_KEY`, `DATABASE_URL`, `ADMIN_API_KEY`, and Supabase settings are never inherited. The model credential stays inside the backend's `LLMProvider` call, outside the workspace.
- **Constrained edit protocol.** The agent has no shell, filesystem, or tools. Its JSON response is validated before any write:
  - it must be a `files` list of `{path, content}` only;
  - paths must be canonical relative POSIX paths. Absolute paths, drive letters, `..`, `.`, empty segments, backslashes, and NUL are rejected;
  - paths must be in the editable-file allowlist;
  - there must be no duplicates, and limits on file count and per-file size apply;
  - an empty or unchanged edit set is rejected.
- **Structured output is not authorization.** Responsive Hero requests Groq strict JSON Schema output to make the wire shape reliable, and the provider adapter revalidates the returned JSON. This does not replace the application validator above: path allowlisting, canonicalization, duplicate detection, byte/file limits, meaningful-change checks, and workspace confinement remain authoritative even if a provider guarantees schema adherence.
- **Path confinement at write time.** Independently of validation, the workspace writes only allowlisted files that already exist. It refuses any path whose components are symlinks, or whose resolved target leaves the workspace root. Starter projects containing links are refused.
- **No agent-authored code executes.** Editable files are HTML and CSS. The build script is fixed and not editable, and it rejects `<script>`, frames, embeds, extra stylesheet links, external or absolute URLs, and `@import`. Chromium runs with JavaScript disabled, and a request filter aborts every request except `file:` URLs inside the build output directory. That blocks network access and local-file disclosure through iframes, images, or stylesheets.
- **Timeouts.** Agent (90 s, an infrastructure `504`), build (20 s), and browser (20 s) timeouts are enforced. Build and browser failures or timeouts return a sanitized `503 application_environment_unavailable` and are never scored.
- **Hidden checks.** Hidden check logic is server code, never copied into the workspace or shown to the agent. The agent receives only the player prompt and the editable files, not the objective or any check. Submit responses cannot represent check IDs, labels, messages, logs, or changed files.
- **Artifact safety.** Build logs replace workspace and other absolute paths with placeholders and are truncated (2000 characters). Screenshots are rendered in memory and returned inline as PNG data URIs; they are neither stored nor served from a public path. Changed-file summaries contain only allowlisted relative paths and line counts, never source.
- **Starter previews.** The public starter-preview route serves only committed PNGs for known viewports of published APPLICATION challenges. They contain no hidden information.
- **Resource abuse controls.** APPLICATION Run and Submit use only the bearer-token-derived local user identity. A per-user PostgreSQL advisory lock covers model/workspace/browser execution across server instances, and durable per-kind cooldown rows prevent process restarts from bypassing throttling. Client IDs, challenge versions, and cooldown values are never accepted as authority.
- **Submit replay safety.** APPLICATION Submit idempotency keys are SHA-256 hashed and scoped to the verified user and authoritative challenge version. The completed replay record is written in the same transaction as submission, progress, and XP. Failed infrastructure work removes its incomplete reservation but retains the execution cooldown. Structured output and browser controls remain independent defense layers.

**Known platform limits.** This is process-level isolation, not a sandbox: there are no OS-enforced CPU, memory, or process limits, and no container or VM boundary. It is acceptable only because no agent-authored code runs. Any challenge where the agent writes executable code (JavaScript, a build config, tests) requires the sandbox decision recorded in [CHALLENGE_TYPES.md](CHALLENGE_TYPES.md#deferred-decisions) first.

## Future application and image challenges — requirements

The requirements below still apply to any broader application platform or image family.

### Execution isolation

- Code written by an AI coding agent is untrusted. It never runs in the FastAPI process, the Next.js server, or any environment holding backend configuration.
- Each attempt runs in a fresh, disposable, isolated workspace with enforced time, CPU, memory, disk, and process limits, and is destroyed afterwards.
- Execution environments receive no production or development secrets: no `GROQ_API_KEY`, `DATABASE_URL`, `ADMIN_API_KEY`, Supabase configuration, or cloud credentials. Any model credential the coding agent needs must be scoped, and must not be readable by code the agent generates.
- Workspaces have no access to the application database or internal infrastructure, and network access is denied by default. Any allowance (for example a pinned dependency mirror) is explicit and narrow.
- Workspaces are never shared between players or attempts.
- The sandbox technology is an open decision. It must be chosen and documented, with its threat model, before implementation.

### Hidden evaluation integrity

- Hidden check files, hidden inputs, and hidden reference data never enter the workspace while the agent runs. They are introduced, or run externally, only after the agent stops.
- Submit responses never include raw hidden test names, assertion messages, selectors, stack traces, logs, or screenshots produced by hidden checks. Trusted code maps hidden outcomes to generalized categories.
- An agent that modifies or deletes pre-existing tests, check configuration, or files outside the allowed scope must not gain a passing result from doing so.

### Artifacts and results

- Artifacts (patches, logs, screenshots, previews, generated images) are classified as Run-visible, Submit-safe, or internal before storage, and only permitted classes reach a response.
- Logs are sanitized before storage or display. They must not contain secrets, environment details, or hidden-check content.
- A live application preview is served from an isolated origin with no access to DR. PROMPT cookies, sessions, or APIs.
- Stored artifacts are owned by the verified local user and are subject to retention limits. Image challenge targets' generation prompts and configuration remain server-only.

## Authentication and tokens

- Supabase Auth owns Google OAuth credentials, password hashes, and sessions; DR. PROMPT stores only a provider identity reference and safe profile metadata.
- FastAPI verifies asymmetric access-token signatures with the project's public JWKS. It also requires an allowed algorithm, expiration, issuer, audience, and non-blank subject.
- The JWKS is cached in process for ten minutes. Unknown key IDs force one refresh. Network or malformed-JWKS failures fail closed with a sanitized service error.
- Missing, malformed, expired, incorrectly signed, or otherwise invalid tokens return `401` with `WWW-Authenticate: Bearer`. Tokens and cryptographic exception details are never returned or logged.
- The stable external identity is `(supabase, sub)`, never email. Email changes synchronize safe metadata without changing ownership.
- The local users uniqueness constraint protects concurrent first access. Existing pre-auth development submissions may remain ownerless; new Submit use-case records always contain the verified local user ID.
- XP milestone uniqueness is enforced by `(user_id, challenge_id, reason)`, and one progress row is enforced per `(user_id, challenge_id)`. The authenticated `/me/progress` query is always scoped to the verified local UUID.
- The frontend contains only `NEXT_PUBLIC_SUPABASE_URL` and the publishable Supabase key. Service-role/secret keys, `DATABASE_URL`, and `GROQ_API_KEY` must never enter browser environment variables or bundles.
- The backend needs `SUPABASE_URL` for issuer/JWKS derivation but no Supabase service-role key and no Supabase SDK.

## Admin challenge data

- Every `/api/v1/admin/*` route passes through one constant-time `X-Admin-Key` authorization dependency. The key is never logged or returned.
- Next.js keeps `ADMIN_API_KEY` server-only. An unlock form is processed on the server and yields an HttpOnly, SameSite=Strict session proof; browser JavaScript uses a protected same-origin BFF and never receives the configured key.
- Admin detail and test responses may contain hidden cases. These shapes exist only under the protected admin namespace; public challenge, Run, Submit, progress, profile, and leaderboard schemas cannot represent them.
- The admin test use case has no submission, XP, progress, or leaderboard write dependency. It returns authoring diagnostics only.
- Published versions are immutable through the application and repository boundaries. New semantic edits require a draft version, preserving historical submission attribution.

## Trusted packages and checks

Package IDs resolve only through an explicit immutable catalog. Filesystem traversal, absolute paths, directory/starter/manifest/preview links and junctions are rejected. JSONB is parsed strictly and validated against package policy before execution. A package owns the HTML/CSS edit universe, build argv, source/output entry, measurement views, check presets, and resource ceilings; admin can narrow permissions, never expand them. Private measurement views cannot become screenshot artifacts.

Admin accepts no build commands, evaluator source, selectors, Python, JavaScript, shell, SQL, or expression language. Trusted measurement JavaScript is fixed repository code receiving selectors as data; page JavaScript, service workers, and downloads are disabled. Hidden checks remain outside the agent workspace. The protected catalog returns authoring metadata without server paths, evaluator source, or secrets. Published package semantics require a new package/version rather than an in-place replacement. See [APPLICATION_PLATFORM.md](APPLICATION_PLATFORM.md).
