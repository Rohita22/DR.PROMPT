# Database

DR. PROMPT uses PostgreSQL through vendor-neutral repository ports. Supabase is the intended managed host, but the backend connects with SQLAlchemy and `asyncpg`; application and domain modules do not import a Supabase SDK or SQLAlchemy.

## Schema

- `challenges`: stable identity, unique slug, track, ordering, and current version label.
- `challenge_versions`: versioned playable content plus JSONB model, evaluation, and scoring configuration. `(challenge_id, version)` is unique. `challenge_type` records the challenge family (`text`, `application`, or `image`, enforced by a check constraint). `text` and `application` are executable. `application_config` (JSONB, nullable) stores the versioned APPLICATION execution configuration: a starter-project reference, editable files, build argv, build output, visible and hidden check IDs, and limits. It is `NULL` for TEXT. Project source is never stored in rows.
- `visible_examples`: ordered explanatory examples.
- `visible_test_cases`: ordered executable Run cases.
- `hidden_test_cases`: ordered server-only Submit cases in a physically separate table.
- `users`: local application UUID identity, unique Supabase provider subject, optional email/username metadata, and timezone-aware timestamps.
- `application_execution_cooldowns`: at most two bounded rows per user (`run` and `submit`) recording the last APPLICATION execution start for cross-instance cooldown enforcement.
- `application_submit_requests`: durable APPLICATION Submit idempotency reservations, uniquely scoped by user, exact challenge-version UUID, and hashed key. Completed rows reference one authoritative submission and retain its safe response payload; failed infrastructure reservations are deleted.
- `submissions`: completed authoritative attempts, aggregate score components, exact challenge/version reference, model identity/configuration version, player prompt, local user ownership, and timezone-aware timestamp.
- `user_progress`: one row per user/challenge with attempts, score-driven best submission, best score, independently monotonic best stars, and first completion timestamp.
- `xp_transactions`: append-only milestone awards referencing their user, challenge, and originating submission. `(user_id, challenge_id, reason)` is unique.

JSONB is limited to values whose domain shape is intrinsically structured: example/test values, grader configuration, and versioned model/scoring configuration. Stable relational identities, ordering, publication state, metrics, and timestamps remain typed columns.

## Configuration

Set a backend-only URL using the async driver:

```text
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/database
```

Supabase connection strings should be adapted to this SQLAlchemy URL form. Never expose this value through a `NEXT_PUBLIC_*` variable.

## Migrations

From `backend/`:

```powershell
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic current
```

The initial migration creates challenge/evaluation persistence. `0002_add_authenticated_users` adds users and submission ownership. `0003_add_progression` adds the progress and XP ledger tables plus milestone/progress uniqueness constraints. Existing pre-auth submissions remain nullable; application logic requires ownership for all new authoritative submissions.
`0004_add_leaderboard_index` adds a partial composite index over owned submissions for exact version/model eligibility and deterministic ranking order.
`0005_add_challenge_type` adds `challenge_versions.challenge_type` with server default `text`, which classifies every existing version, including the five CONTROL challenges, as TEXT. It also adds the `ck_challenge_versions_challenge_type` check constraint. Mappers reject unknown stored values as a sanitized persistence error.
`0006_add_application_config` adds the nullable `challenge_versions.application_config` JSONB column. Existing TEXT rows keep `NULL`.

`0007_add_application_execution_guard` adds the two narrow APPLICATION coordination tables. Session-level advisory locks require no table and are held on a dedicated database connection without holding an execution-long transaction.

## Development seed

After migrations, explicitly seed the five-challenge CONTROL path:

```powershell
uv run python -m app.infrastructure.database.seed
```

The seed also installs the APPLICATION packages (`responsive-hero`, CONTROL order 6, and `pricing-grid`, order 7, no hidden test rows because its hidden checks are server code). It writes each version's `challenge_type` and `application_config` explicitly and uses stable identities, deterministic UUIDs, and PostgreSQL upserts. It is idempotent, never runs during application startup, and does not delete submissions, progress, or XP. Each TEXT version 1 challenge has explanatory examples, three visible tests, and six hidden tests. Existing `exact-output` identity and version references are preserved.

No schema migration was needed for unlocking: `challenges.track` and `challenges.sort_order` already define each published linear path, while completion is derived from `user_progress.best_stars`.

## Repository mapping and transactions

Persistence rows are mapped explicitly to immutable domain objects. The public challenge reader reconstructs a published `PlayableChallenge` without querying hidden cases. The hidden-suite reader loads only an exact challenge/version pair. The user repository atomically finds or creates a local user by `(auth_provider, auth_provider_user_id)` and safely synchronizes a present email.

An authoritative Submit uses one database transaction for submission, progress, and XP. The local user row is locked to serialize that user's progression writes; the adapter then inserts the submission, updates or creates progress, appends new milestone rows, and calculates total XP from the ledger. Any failure rolls back the entire operation and becomes a sanitized persistence error. XP is not cached on `users`.

For APPLICATION Submit, that transaction also marks the pre-created idempotency reservation completed, links the submission, and stores the safe replay payload. This closes the crash window between awarding XP and recording replay state. Cooldown rows are bounded by `(user_id, execution_kind)`, so no event-log cleanup worker is required. Completed idempotency rows follow the lifetime of their referenced authoritative submissions; stale in-progress rows are replaced opportunistically after the configured timeout.

Normal unit/application tests use in-memory repositories and require no database. PostgreSQL integration tests are opt-in with a dedicated disposable `TEST_DATABASE_URL`; SQLite is not used as a substitute for PostgreSQL JSONB, UUID, or constraint behavior.

`PostgresAdminChallengeRepository` maps the same tables into an admin authoring record containing one selected draft/current version plus version history. Draft edits replace only that draft's ordered examples and test rows. Publishing retires the prior published row and updates `challenges.current_version` in one transaction. Unpublishing retires the active version and clears the pointer. Neither operation deletes versions, submissions, progress, or XP. Track/order conflicts are rejected rather than silently reordering another challenge.

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://user:password@host:5432/disposable_test_database"
uv run pytest -m integration tests/integration
```

The integration test creates and drops an isolated temporary schema inside that explicitly supplied disposable database.

## Application submissions and leaderboards

APPLICATION submissions use the existing `submissions` table unchanged:

- `passed_tests` / `total_tests` hold passed / total hidden checks;
- `accuracy` holds the normalized `evaluation_score`;
- `prompt_tokens`, `efficiency`, `final_score`, and `stars` keep their meaning;
- `model_identifier` / `model_configuration_version` record the coding-agent model configuration.

I kept the column name `accuracy` for compatibility rather than renaming it. For TEXT it is literally pass-rate accuracy; for APPLICATION it is the normalized functional score. Leaderboards are strictly per challenge version and model configuration, so the two meanings are never ranked against each other. Existing TEXT rows and queries are untouched. The leaderboard API still names the field `accuracy`; the player UI labels it by challenge type. No migration was needed for submissions.

## Leaderboard query

Challenge leaderboards are derived from `submissions`; there is no duplicated leaderboard table. The PostgreSQL adapter filters to the active challenge version, model identifier, and model configuration version. A first `row_number()` window selects the best row per user by `final_score DESC, accuracy DESC, prompt_tokens ASC, created_at ASC, id ASC`. A second window assigns deterministic unique global positions using the same order. Offset pagination is bounded to 100 rows, while an authenticated user's position is selected independently so it remains visible outside the requested page. Historical and incompatible submissions remain persisted but are not comparable and therefore do not enter the active leaderboard.

## Security

`hidden_test_cases` and authoritative `submissions` are backend-only tables. Browsers should not receive database credentials or query them directly. Future Supabase RLS must deny browser roles access to these tables even though the FastAPI repository boundary remains the primary access path.

## Application Platform v1 configuration

No challenge-specific table was added. Existing `application_config` JSONB now carries `schema_version: 1`, the registered package reference in `starter_project`, the effective editable/check selections, `viewports` with safe screenshot flags/labels, and execution limits. Source/build settings remain reproducibility metadata and must equal package policy. Strict mapping rejects malformed or unknown-version JSONB and policy expansion before execution. Admin draft updates persist this configuration independently of TEXT case rows; publication validates APPLICATION configuration instead of demanding text test rows. Type is immutable through draft updates.

`0008_application_platform`, after `0007_add_application_execution_guard`, backfills only schema/versioned viewport representation for legacy Responsive Hero rows. Its identity, version label, model configuration, four/nine check sets, and all submissions/progress/XP remain unchanged. This is a representation migration, so no new Hero version is needed. Downgrade removes the additive fields on Hero; new Pricing Grid content requires the v1 runtime. Future material package changes require new immutable package and challenge versions.

The explicit seed adds Pricing Grid at order 7 using the existing schema. Profile totals and per-challenge leaderboard eligibility remain query-derived. Screenshot replay payloads now preserve optional labels and use the actual artifact `png` field, while replaying earlier records without a label remains supported.
