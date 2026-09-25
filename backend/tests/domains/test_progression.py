import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.domains.challenges.models import Difficulty
from app.domains.progression import (
    ProgressionService,
    XPAwardReason,
    XPRewardConfiguration,
)
from app.domains.submissions import Submission
from app.infrastructure.submissions import InMemorySubmissionRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)
USER_ID = "11111111-1111-4111-8111-111111111111"
CHALLENGE_ID = "control-exact-output"


def submission(*, submission_id: str, score: float, stars: int, at: datetime = NOW) -> Submission:
    return Submission(
        id=submission_id,
        challenge_id=CHALLENGE_ID,
        challenge_version_id="1",
        user_id=USER_ID,
        prompt="Return YES or NO.",
        prompt_tokens=5,
        passed_tests=6 if stars == 3 else 5,
        total_tests=6,
        accuracy=100 if stars == 3 else 83.33,
        efficiency=100,
        final_score=score,
        stars=stars,
        model_identifier="openai/gpt-oss-20b",
        model_configuration_version="1",
        created_at=at,
    )


@pytest.mark.parametrize(
    ("stars", "existing", "expected_reasons", "expected_xp"),
    [
        (0, frozenset(), (), 0),
        (1, frozenset(), (XPAwardReason.FIRST_COMPLETION,), 100),
        (1, frozenset({XPAwardReason.FIRST_COMPLETION}), (), 0),
        (2, frozenset(), (XPAwardReason.FIRST_COMPLETION, XPAwardReason.TWO_STAR), 125),
        (2, frozenset({XPAwardReason.FIRST_COMPLETION}), (XPAwardReason.TWO_STAR,), 25),
        (
            3,
            frozenset(),
            (
                XPAwardReason.FIRST_COMPLETION,
                XPAwardReason.TWO_STAR,
                XPAwardReason.THREE_STAR,
            ),
            175,
        ),
        (
            3,
            frozenset({XPAwardReason.FIRST_COMPLETION, XPAwardReason.TWO_STAR}),
            (XPAwardReason.THREE_STAR,),
            50,
        ),
        (3, frozenset(XPAwardReason), (), 0),
    ],
)
def test_milestone_awards_are_incremental(
    stars: int,
    existing: frozenset[XPAwardReason],
    expected_reasons: tuple[XPAwardReason, ...],
    expected_xp: int,
) -> None:
    awards = ProgressionService().new_awards(
        stars=stars,
        difficulty=Difficulty.EASY,
        awarded_reasons=existing,
        configuration=XPRewardConfiguration(),
    )

    assert tuple(award.reason for award in awards) == expected_reasons
    assert sum(award.amount for award in awards) == expected_xp


def test_boss_completion_replaces_first_completion_by_default() -> None:
    awards = ProgressionService().new_awards(
        stars=1,
        difficulty=Difficulty.BOSS,
        awarded_reasons=frozenset(),
        configuration=XPRewardConfiguration(),
    )

    assert [(award.reason, award.amount) for award in awards] == [
        (XPAwardReason.BOSS_COMPLETION, 250)
    ]


def test_custom_rewards_and_additive_boss_first_completion_are_supported() -> None:
    awards = ProgressionService().new_awards(
        stars=3,
        difficulty=Difficulty.BOSS,
        awarded_reasons=frozenset(),
        configuration=XPRewardConfiguration(
            first_completion=10,
            two_star=20,
            three_star=30,
            boss_completion=40,
            boss_replaces_first_completion=False,
        ),
    )

    assert [(award.reason, award.amount) for award in awards] == [
        (XPAwardReason.BOSS_COMPLETION, 40),
        (XPAwardReason.FIRST_COMPLETION, 10),
        (XPAwardReason.TWO_STAR, 20),
        (XPAwardReason.THREE_STAR, 30),
    ]


def test_zero_value_reward_disables_that_milestone() -> None:
    awards = ProgressionService().new_awards(
        stars=2,
        difficulty=Difficulty.EASY,
        awarded_reasons=frozenset(),
        configuration=XPRewardConfiguration(first_completion=0),
    )

    assert [award.reason for award in awards] == [XPAwardReason.TWO_STAR]


def test_progress_tracks_attempts_monotonic_bests_and_first_completion_time() -> None:
    service = ProgressionService()
    first = submission(submission_id="00000000-0000-4000-8000-000000000001", score=80, stars=0)
    progress = service.update_progress(submission=first, existing=None, occurred_at=NOW)

    assert progress.attempts == 1
    assert progress.completed_at is None
    assert progress.best_submission_id == first.id

    completion_time = NOW + timedelta(minutes=1)
    second = submission(
        submission_id="00000000-0000-4000-8000-000000000002",
        score=90,
        stars=2,
        at=completion_time,
    )
    progress = service.update_progress(
        submission=second, existing=progress, occurred_at=completion_time
    )
    assert progress.attempts == 2
    assert progress.best_score == 90
    assert progress.best_stars == 2
    assert progress.best_submission_id == second.id
    assert progress.completed_at == completion_time

    third_time = NOW + timedelta(minutes=2)
    third = submission(
        submission_id="00000000-0000-4000-8000-000000000003",
        score=85,
        stars=3,
        at=third_time,
    )
    progress = service.update_progress(submission=third, existing=progress, occurred_at=third_time)
    assert progress.attempts == 3
    assert progress.best_score == 90
    assert progress.best_stars == 3
    assert progress.best_submission_id == second.id
    assert progress.completed_at == completion_time

    tied = replace(third, id="00000000-0000-4000-8000-000000000004", final_score=90)
    progress = service.update_progress(
        submission=tied,
        existing=progress,
        occurred_at=NOW + timedelta(minutes=3),
    )
    assert progress.best_submission_id == second.id


def test_in_memory_transaction_prevents_duplicate_milestones_under_concurrency() -> None:
    repository = InMemorySubmissionRepository()
    first = submission(submission_id="00000000-0000-4000-8000-000000000010", score=100, stars=3)
    second = replace(first, id="00000000-0000-4000-8000-000000000011")

    async def execute() -> tuple[int, int]:
        results = await asyncio.gather(
            repository.save_with_progression(
                first,
                difficulty=Difficulty.EASY,
                xp_configuration=XPRewardConfiguration(),
            ),
            repository.save_with_progression(
                second,
                difficulty=Difficulty.EASY,
                xp_configuration=XPRewardConfiguration(),
            ),
        )
        return results[0].xp_earned, results[1].xp_earned

    earned = asyncio.run(execute())

    assert sorted(earned) == [0, 175]
    assert len(repository.progress) == 1
    assert len(repository.xp_transactions) == 3
    assert next(iter(repository.progress.values())).attempts == 2
