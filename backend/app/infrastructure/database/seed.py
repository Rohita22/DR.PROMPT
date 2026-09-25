"""Explicit, idempotent development seed for the CONTROL progression path."""

import asyncio
import uuid

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domains.challenges.models import PlayableChallenge
from app.domains.evaluation.test_cases import HiddenTestSuite
from app.infrastructure.challenges.control_fixtures import (
    CONTROL_CHALLENGES,
    CONTROL_HIDDEN_TEST_SUITES,
)
from app.infrastructure.database.mappers import (
    grader_config_to_data,
    model_config_to_data,
    scoring_config_to_data,
)
from app.infrastructure.database.models import (
    ChallengeRow,
    ChallengeVersionRow,
    HiddenTestCaseRow,
    VisibleExampleRow,
    VisibleTestCaseRow,
)
from app.infrastructure.database.session import create_session_factory

_SEED_NAMESPACE = uuid.UUID("e894e9b3-91c6-47c6-8045-a56dc2be14ae")


def _seed_id(label: str) -> uuid.UUID:
    return uuid.uuid5(_SEED_NAMESPACE, label)


async def seed(settings: Settings | None = None) -> None:
    factory = create_session_factory(settings or Settings())

    async with factory() as session, session.begin():
        for playable in CONTROL_CHALLENGES:
            await _seed_playable(
                session,
                playable,
                CONTROL_HIDDEN_TEST_SUITES[playable.challenge.id],
            )


async def _seed_playable(
    session: AsyncSession,
    playable: PlayableChallenge,
    hidden_suite: HiddenTestSuite,
) -> None:
    challenge = playable.challenge
    version = playable.version
    version_row_id = _seed_id(f"{challenge.id}:{version.version_id}")
    challenge_insert = insert(ChallengeRow).values(
        id=challenge.id,
        slug=challenge.slug,
        track=challenge.track.value,
        sort_order=challenge.order,
        current_version=version.version_id,
    )
    await session.execute(
        challenge_insert.on_conflict_do_update(
            index_elements=[ChallengeRow.id],
            set_={
                "slug": challenge_insert.excluded.slug,
                "track": challenge_insert.excluded.track,
                "sort_order": challenge_insert.excluded.sort_order,
                "current_version": challenge_insert.excluded.current_version,
                "updated_at": func.now(),
            },
        )
    )

    version_insert = insert(ChallengeVersionRow).values(
        id=version_row_id,
        challenge_id=challenge.id,
        version=version.version_id,
        title=version.title,
        description=version.description,
        objective=version.objective,
        constraints=list(version.constraints),
        difficulty=version.difficulty.value,
        prompt_token_limit=version.prompt_token_limit,
        evaluation_config={
            "default_grader": grader_config_to_data(version.evaluation_config.default_grader)
        },
        model_config=model_config_to_data(version.model_config),
        scoring_config=scoring_config_to_data(version.scoring_config),
        publication_state=version.publication_state.value,
    )
    version_row_id = (
        await session.execute(
            version_insert.on_conflict_do_update(
                constraint="uq_challenge_version",
                set_={
                    "title": version_insert.excluded.title,
                    "description": version_insert.excluded.description,
                    "objective": version_insert.excluded.objective,
                    "constraints": version_insert.excluded.constraints,
                    "difficulty": version_insert.excluded.difficulty,
                    "prompt_token_limit": version_insert.excluded.prompt_token_limit,
                    "evaluation_config": version_insert.excluded.evaluation_config,
                    "model_config": version_insert.excluded.model_config,
                    "scoring_config": version_insert.excluded.scoring_config,
                    "publication_state": version_insert.excluded.publication_state,
                },
            ).returning(ChallengeVersionRow.id)
        )
    ).scalar_one()

    for row_type in (VisibleExampleRow, VisibleTestCaseRow, HiddenTestCaseRow):
        await session.execute(
            delete(row_type).where(row_type.challenge_version_id == version_row_id)
        )

    session.add_all(
        VisibleExampleRow(
            id=_seed_id(f"{challenge.id}:example:{index}"),
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
            id=_seed_id(f"{challenge.id}:visible:{test.id}"),
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
            id=_seed_id(f"{challenge.id}:hidden:{test.id}"),
            challenge_version_id=version_row_id,
            test_id=test.id,
            input=test.input,
            expected_output=test.expected_output,
            evaluation_config=grader_config_to_data(test.grader_config),
            sort_order=index,
        )
        for index, test in enumerate(hidden_suite.test_cases, start=1)
    )


if __name__ == "__main__":
    asyncio.run(seed())
