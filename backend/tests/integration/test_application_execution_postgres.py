import asyncio
import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.application.challenges.execution_guard import (
    ApplicationExecutionKind,
    ApplicationExecutionScope,
)
from app.core.exceptions import (
    ApplicationExecutionInProgressError,
    ApplicationRateLimitError,
)
from app.infrastructure.database.application_execution import (
    PostgresApplicationExecutionCoordinator,
)
from app.infrastructure.database.models import Base, ChallengeRow, ChallengeVersionRow, UserRow

_TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not _TEST_DATABASE_URL:
    pytest.skip(
        "Set TEST_DATABASE_URL to a dedicated disposable PostgreSQL database.",
        allow_module_level=True,
    )

pytestmark = pytest.mark.integration


async def exercise() -> None:
    schema = f"dr_prompt_guard_{uuid.uuid4().hex}"
    admin = create_async_engine(_TEST_DATABASE_URL)
    async with admin.begin() as connection:
        await connection.execute(CreateSchema(schema))
    engine = create_async_engine(
        _TEST_DATABASE_URL,
        connect_args={"server_settings": {"search_path": schema}},
    )
    user_a, user_b, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                UserRow.__table__.insert(),
                [
                    {"id": user_a, "auth_provider": "supabase", "auth_provider_user_id": "a"},
                    {"id": user_b, "auth_provider": "supabase", "auth_provider_user_id": "b"},
                ],
            )
            await connection.execute(
                ChallengeRow.__table__.insert(),
                {
                    "id": "guard-challenge",
                    "slug": "guard-challenge",
                    "track": "control",
                    "sort_order": 1,
                    "current_version": "1",
                },
            )
            await connection.execute(
                ChallengeVersionRow.__table__.insert(),
                {
                    "id": version_id,
                    "challenge_id": "guard-challenge",
                    "version": "1",
                    "title": "Guard",
                    "description": "Guard",
                    "objective": "Guard",
                    "constraints": [],
                    "difficulty": "easy",
                    "evaluation_config": {},
                    "model_config": {},
                    "scoring_config": {},
                    "publication_state": "published",
                    "challenge_type": "application",
                    "application_config": {},
                },
            )
        coordinator = PostgresApplicationExecutionCoordinator(engine)
        scope_a = ApplicationExecutionScope(str(user_a), "guard-challenge", "guard-challenge", "1")
        scope_b = ApplicationExecutionScope(str(user_b), "guard-challenge", "guard-challenge", "1")
        async with coordinator.start(
            scope_a,
            kind=ApplicationExecutionKind.RUN,
            cooldown_seconds=10,
            stale_after_seconds=180,
        ):
            with pytest.raises(ApplicationExecutionInProgressError):
                async with coordinator.start(
                    scope_a,
                    kind=ApplicationExecutionKind.SUBMIT,
                    cooldown_seconds=20,
                    stale_after_seconds=180,
                    idempotency_key_hash="a" * 64,
                ):
                    pass
            async with coordinator.start(
                scope_b,
                kind=ApplicationExecutionKind.RUN,
                cooldown_seconds=10,
                stale_after_seconds=180,
            ):
                pass
        with pytest.raises(ApplicationRateLimitError):
            async with coordinator.start(
                scope_a,
                kind=ApplicationExecutionKind.RUN,
                cooldown_seconds=10,
                stale_after_seconds=180,
            ):
                pass
        with pytest.raises(TimeoutError):
            async with coordinator.start(
                scope_a,
                kind=ApplicationExecutionKind.SUBMIT,
                cooldown_seconds=0,
                stale_after_seconds=180,
                idempotency_key_hash="b" * 64,
            ):
                raise TimeoutError
        async with coordinator.start(
            scope_a,
            kind=ApplicationExecutionKind.SUBMIT,
            cooldown_seconds=0,
            stale_after_seconds=180,
            idempotency_key_hash="b" * 64,
        ):
            pass
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await admin.dispose()


def test_postgres_application_coordination() -> None:
    asyncio.run(exercise())
