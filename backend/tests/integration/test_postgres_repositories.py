import asyncio
import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.domains.auth import AuthenticatedIdentity, AuthProvider
from app.domains.challenges.models import PublicationState
from app.domains.progression import XPRewardConfiguration
from app.domains.submissions import Submission
from app.infrastructure.challenges.in_memory_hidden_test_repository import (
    EXACT_OUTPUT_HIDDEN_TEST_SUITE,
)
from app.infrastructure.challenges.in_memory_repository import EXACT_OUTPUT_CHALLENGE
from app.infrastructure.database.mappers import (
    grader_config_to_data,
    model_config_to_data,
    scoring_config_to_data,
)
from app.infrastructure.database.models import (
    Base,
    ChallengeRow,
    ChallengeVersionRow,
    HiddenTestCaseRow,
    SubmissionRow,
    UserProgressRow,
    UserRow,
    VisibleExampleRow,
    VisibleTestCaseRow,
    XPTransactionRow,
)
from app.infrastructure.database.repositories import (
    PostgresChallengeRepository,
    PostgresHiddenTestSuiteRepository,
    PostgresSubmissionRepository,
    PostgresUserProgressRepository,
)
from app.infrastructure.database.user_repository import PostgresUserRepository

_TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not _TEST_DATABASE_URL:
    pytest.skip(
        "Set TEST_DATABASE_URL to a dedicated disposable PostgreSQL database.",
        allow_module_level=True,
    )

pytestmark = pytest.mark.integration


async def _exercise_repositories() -> None:
    schema = f"dr_prompt_test_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(_TEST_DATABASE_URL)
    async with admin_engine.begin() as connection:
        await connection.execute(CreateSchema(schema))

    engine = create_async_engine(
        _TEST_DATABASE_URL,
        connect_args={"server_settings": {"search_path": schema}},
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            source = EXACT_OUTPUT_CHALLENGE
            version = source.version
            version_row_id = uuid.uuid4()
            session.add(
                ChallengeRow(
                    id=source.challenge.id,
                    slug=source.challenge.slug,
                    track=source.challenge.track.value,
                    sort_order=source.challenge.order,
                    current_version=version.version_id,
                )
            )
            session.add(
                ChallengeVersionRow(
                    id=version_row_id,
                    challenge_id=source.challenge.id,
                    version=version.version_id,
                    title=version.title,
                    description=version.description,
                    objective=version.objective,
                    constraints=list(version.constraints),
                    difficulty=version.difficulty.value,
                    prompt_token_limit=version.prompt_token_limit,
                    evaluation_config={
                        "default_grader": grader_config_to_data(
                            version.evaluation_config.default_grader
                        )
                    },
                    model_config=model_config_to_data(version.model_config),
                    scoring_config=scoring_config_to_data(version.scoring_config),
                    publication_state=version.publication_state.value,
                )
            )
            session.add_all(
                VisibleExampleRow(
                    challenge_version_id=version_row_id,
                    input=example.input,
                    expected_output=example.expected_output,
                    explanation=example.explanation,
                    sort_order=index,
                )
                for index, example in enumerate(version.visible_examples, start=1)
            )
            session.add_all(
                VisibleTestCaseRow(
                    challenge_version_id=version_row_id,
                    test_id=test.id,
                    input=test.input,
                    expected_output=test.expected_output,
                    evaluation_config=grader_config_to_data(test.grader_config),
                    sort_order=index,
                )
                for index, test in enumerate(version.visible_test_cases, start=1)
            )
            session.add_all(
                HiddenTestCaseRow(
                    challenge_version_id=version_row_id,
                    test_id=test.id,
                    input=test.input,
                    expected_output=test.expected_output,
                    evaluation_config=grader_config_to_data(test.grader_config),
                    sort_order=index,
                )
                for index, test in enumerate(
                    EXACT_OUTPUT_HIDDEN_TEST_SUITE.test_cases,
                    start=1,
                )
            )
            await session.commit()

            public_repository = PostgresChallengeRepository(session)
            hidden_repository = PostgresHiddenTestSuiteRepository(session)
            playable = await public_repository.get_by_slug("exact-output")
            assert playable == source
            assert await public_repository.list_published() == (source,)
            assert not hasattr(playable, "hidden_test_suite")
            assert await public_repository.get_by_slug("missing") is None

            hidden = await hidden_repository.get_for_version(source.challenge.id, "1")
            assert hidden == EXACT_OUTPUT_HIDDEN_TEST_SUITE
            assert await hidden_repository.get_for_version(source.challenge.id, "2") is None

            user_repository = PostgresUserRepository(session)
            user = await user_repository.synchronize(
                AuthenticatedIdentity(
                    AuthProvider.SUPABASE,
                    "integration-provider-user",
                    "old@example.com",
                )
            )
            synchronized = await user_repository.synchronize(
                AuthenticatedIdentity(
                    AuthProvider.SUPABASE,
                    "integration-provider-user",
                    "new@example.com",
                )
            )
            assert synchronized.id == user.id
            assert synchronized.email == "new@example.com"
            async with session.begin():
                user_count = await session.scalar(select(func.count()).select_from(UserRow))
            assert user_count == 1

            submission = Submission(
                id=str(uuid.uuid4()),
                challenge_id=source.challenge.id,
                challenge_version_id="1",
                user_id=user.id,
                prompt="Return YES or NO.",
                prompt_tokens=5,
                passed_tests=6,
                total_tests=6,
                accuracy=100,
                efficiency=100,
                final_score=100,
                stars=3,
                model_identifier=version.model_config.model_id,
                model_configuration_version=version.model_config.configuration_version,
                created_at=datetime.now(UTC),
            )
            progression = await PostgresSubmissionRepository(session).save_with_progression(
                submission,
                difficulty=version.difficulty,
                xp_configuration=XPRewardConfiguration(),
            )
            assert progression.xp_earned == 175
            assert progression.total_xp == 175
            persisted = await session.scalar(
                select(SubmissionRow).where(SubmissionRow.id == uuid.UUID(submission.id))
            )
            assert persisted is not None
            assert persisted.prompt == submission.prompt
            assert persisted.prompt_tokens == submission.prompt_tokens
            assert persisted.final_score == submission.final_score
            assert persisted.model_identifier == submission.model_identifier
            assert str(persisted.user_id) == user.id
            progress = await session.scalar(select(UserProgressRow))
            assert progress is not None
            assert progress.attempts == 1
            assert progress.best_score == 100
            assert progress.best_stars == 3
            assert await session.scalar(select(func.count()).select_from(XPTransactionRow)) == 3
            await session.rollback()
            summary = await PostgresUserProgressRepository(session).get_summary(user.id)
            assert summary.total_xp == 175
            assert summary.challenges_completed == 1
            assert summary.stars_earned == 3
            assert summary.challenges[0].challenge_slug == "exact-output"

            duplicate = XPTransactionRow(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user.id),
                challenge_id=source.challenge.id,
                submission_id=uuid.UUID(submission.id),
                reason="first_completion",
                amount=100,
                created_at=datetime.now(UTC),
            )
            with pytest.raises(IntegrityError):
                async with session.begin():
                    session.add(duplicate)
                    await session.flush()

            duplicate_progress = UserProgressRow(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user.id),
                challenge_id=source.challenge.id,
                best_submission_id=uuid.UUID(submission.id),
                best_score=100,
                best_stars=3,
                attempts=1,
                completed_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            with pytest.raises(IntegrityError):
                async with session.begin():
                    session.add(duplicate_progress)
                    await session.flush()

            version_row = await session.get(ChallengeVersionRow, version_row_id)
            assert version_row is not None
            version_row.publication_state = PublicationState.RETIRED.value
            await session.commit()
            assert await public_repository.get_by_slug("exact-output") is None
            assert await public_repository.list_published() == ()
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await admin_engine.dispose()


def test_postgresql_repository_adapters() -> None:
    asyncio.run(_exercise_repositories())
