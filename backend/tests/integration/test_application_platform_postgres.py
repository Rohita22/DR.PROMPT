"""Opt-in PostgreSQL JSONB authoring, leaderboard, and derived profile coverage."""

import asyncio
import os
import uuid
from dataclasses import replace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.application.admin.models import CreateChallengeCommand, UpdateChallengeDraftCommand
from app.application.admin.use_cases import (
    CreateChallengeUseCase,
    CreateChallengeVersionUseCase,
    PublishChallengeUseCase,
    UnpublishChallengeUseCase,
    UpdateChallengeDraftUseCase,
)
from app.infrastructure.application import StarterProjectRepository
from app.infrastructure.database.admin_repository import PostgresAdminChallengeRepository
from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import PostgresChallengeRepository
from tests.application.test_admin_application import application_spec

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL is not configured"),
]


def test_application_jsonb_draft_publish_and_immutable_history():
    async def exercise():
        schema = f"dr_prompt_platform_{uuid.uuid4().hex}"
        admin_engine = create_async_engine(URL)
        async with admin_engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = create_async_engine(URL, connect_args={"server_settings": {"search_path": schema}})
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                repository, packages = (
                    PostgresAdminChallengeRepository(session),
                    StarterProjectRepository(),
                )
                spec = application_spec("pricing-grid")
                await CreateChallengeUseCase(repository, packages).execute(
                    CreateChallengeCommand(spec)
                )
                config = replace(spec.application, editable_files=("src/styles.css",))
                await UpdateChallengeDraftUseCase(repository, packages).execute(
                    UpdateChallengeDraftCommand(spec.slug, replace(spec, application=config))
                )
                await PublishChallengeUseCase(repository, packages).execute(spec.slug)
                original = await PostgresChallengeRepository(session).get_by_slug(spec.slug)
                assert original.version.application_config.editable_files == ("src/styles.css",)
                await CreateChallengeVersionUseCase(repository).execute(spec.slug)
                await UpdateChallengeDraftUseCase(repository, packages).execute(
                    UpdateChallengeDraftCommand(spec.slug, replace(spec, version="2"))
                )
                # Draft changes cannot change the active version's JSONB.
                assert (
                    await PostgresChallengeRepository(session).get_by_slug(spec.slug)
                ) == original
                await PublishChallengeUseCase(repository, packages).execute(spec.slug)
                assert (
                    await PostgresChallengeRepository(session).get_by_slug(spec.slug)
                ).version.version_id == "2"
                await UnpublishChallengeUseCase(repository).execute(spec.slug)
                assert await PostgresChallengeRepository(session).get_by_slug(spec.slug) is None
                record = await repository.get_by_slug(spec.slug)
                assert len(record.versions) == 2
        finally:
            await engine.dispose()
            async with admin_engine.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
            await admin_engine.dispose()

    asyncio.run(exercise())


def test_two_application_packages_persist_leaderboard_and_profile_totals():
    from datetime import UTC, datetime

    from app.domains.auth import AuthenticatedIdentity, AuthProvider
    from app.domains.progression import XPRewardConfiguration
    from app.domains.submissions import Submission
    from app.infrastructure.challenges.application_fixtures import APPLICATION_CHALLENGES
    from app.infrastructure.challenges.control_fixtures import CONTROL_CHALLENGES
    from app.infrastructure.database.leaderboard_repository import PostgresLeaderboardRepository
    from app.infrastructure.database.profile_repository import PostgresProfileRepository
    from app.infrastructure.database.repositories import PostgresSubmissionRepository
    from app.infrastructure.database.seed import _seed_playable
    from app.infrastructure.database.user_repository import PostgresUserRepository

    async def exercise():
        schema = f"dr_prompt_product_{uuid.uuid4().hex}"
        admin_engine = create_async_engine(URL)
        async with admin_engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = create_async_engine(URL, connect_args={"server_settings": {"search_path": schema}})
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                async with session.begin():
                    for playable in (*CONTROL_CHALLENGES, *APPLICATION_CHALLENGES):
                        await _seed_playable(session, playable, None)
                user = await PostgresUserRepository(session).synchronize(
                    AuthenticatedIdentity(AuthProvider.SUPABASE, "platform-player", None)
                )
                for playable in APPLICATION_CHALLENGES:
                    version = playable.version
                    submission = Submission(
                        id=str(uuid.uuid4()),
                        challenge_id=playable.challenge.id,
                        challenge_version_id=version.version_id,
                        user_id=user.id,
                        prompt="Arrange a responsive layout.",
                        prompt_tokens=42,
                        passed_tests=len(version.application_config.hidden_checks),
                        total_tests=len(version.application_config.hidden_checks),
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
                    board = await PostgresLeaderboardRepository(session).get_page(
                        challenge_id=playable.challenge.id,
                        challenge_version_id=version.version_id,
                        model_identifier=version.model_config.model_id,
                        model_configuration_version=version.model_config.configuration_version,
                        limit=10,
                        offset=0,
                        current_user_id=user.id,
                    )
                    assert board.total_entries == 1
                    assert board.current_user_entry.rank == 1
                    assert board.entries[0].submission_id == submission.id
                profile = await PostgresProfileRepository(session).get_snapshot(
                    user.id, recent_limit=5
                )
                assert profile.published_challenges == 7
                assert profile.total_xp == 350
                assert profile.challenges_completed == 2
                assert profile.stars_earned == 6
                assert profile.three_star_completions == 2
                assert {a.challenge_slug for a in profile.recent_activity} == {
                    "responsive-hero",
                    "pricing-grid",
                }
        finally:
            await engine.dispose()
            async with admin_engine.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
            await admin_engine.dispose()

    asyncio.run(exercise())
