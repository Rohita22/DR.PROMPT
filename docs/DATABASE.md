# Database

DR. PROMPT uses PostgreSQL through vendor-neutral repository ports. Supabase is the intended managed host, but the backend connects with SQLAlchemy and `asyncpg`; application and domain modules do not import a Supabase SDK or SQLAlchemy.

## Schema

- `challenges`: stable identity, unique slug, track, ordering, and current version label.
- `challenge_versions`: versioned playable content plus JSONB model, evaluation, and scoring configuration. `(challenge_id, version)` is unique.
- `visible_examples`: ordered explanatory examples.
- `visible_test_cases`: ordered executable Run cases.
- `hidden_test_cases`: ordered server-only Submit cases in a physically separate table.
- `users`: local application UUID identity, unique Supabase provider subject, optional email/username metadata, and timezone-aware timestamps.
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

## Development seed

After migrations, explicitly seed the five-challenge CONTROL path:

```powershell
uv run python -m app.infrastructure.database.seed
```

The seed uses stable identities, deterministic UUIDs, and PostgreSQL upserts. It is idempotent, never runs during application startup, and does not delete submissions, progress, or XP. Each version 1 challenge has explanatory examples, three visible tests, and six hidden tests. Existing `exact-output` identity and version references are preserved.

No schema migration was needed for unlocking: `challenges.track` and `challenges.sort_order` already define each published linear path, while completion is derived from `user_progress.best_stars`.

## Repository mapping and transactions

Persistence rows are mapped explicitly to immutable domain objects. The public challenge reader reconstructs a published `PlayableChallenge` without querying hidden cases. The hidden-suite reader loads only an exact challenge/version pair. The user repository atomically finds or creates a local user by `(auth_provider, auth_provider_user_id)` and safely synchronizes a present email.

An authoritative Submit uses one database transaction for submission, progress, and XP. The local user row is locked to serialize that user's progression writes; the adapter then inserts the submission, updates or creates progress, appends new milestone rows, and calculates total XP from the ledger. Any failure rolls back the entire operation and becomes a sanitized persistence error. XP is not cached on `users`.

Normal unit/application tests use in-memory repositories and require no database. PostgreSQL integration tests are opt-in with a dedicated disposable `TEST_DATABASE_URL`; SQLite is not used as a substitute for PostgreSQL JSONB, UUID, or constraint behavior.

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://user:password@host:5432/disposable_test_database"
uv run pytest -m integration tests/integration
```

The integration test creates and drops an isolated temporary schema inside that explicitly supplied disposable database.

## Security

`hidden_test_cases` and authoritative `submissions` are backend-only tables. Browsers should not receive database credentials or query them directly. Future Supabase RLS must deny browser roles access to these tables even though the FastAPI repository boundary remains the primary access path.
