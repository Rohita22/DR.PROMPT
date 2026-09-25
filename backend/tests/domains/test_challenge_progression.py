from datetime import UTC, datetime

from app.domains.progression import (
    ChallengeProgressionService,
    ChallengeStatus,
    UserProgressItem,
)
from app.infrastructure.challenges.control_fixtures import CONTROL_HIDDEN_TEST_SUITES
from app.infrastructure.challenges.in_memory_repository import CONTROL_CHALLENGES


def progress(slug: str, stars: int, score: float = 80) -> UserProgressItem:
    return UserProgressItem(
        challenge_slug=slug,
        best_score=score,
        best_stars=stars,
        attempts=1,
        completed_at=datetime.now(UTC) if stars >= 1 else None,
    )


def test_linear_progression_status_semantics() -> None:
    service = ChallengeProgressionService()

    anonymous = service.evaluate_path(CONTROL_CHALLENGES)
    assert [item.status for item in anonymous] == [
        ChallengeStatus.AVAILABLE,
        ChallengeStatus.LOCKED,
        ChallengeStatus.LOCKED,
        ChallengeStatus.LOCKED,
        ChallengeStatus.LOCKED,
    ]

    zero_star = service.evaluate_path(
        CONTROL_CHALLENGES,
        (progress("exact-output", 0),),
    )
    assert zero_star[0].status is ChallengeStatus.AVAILABLE
    assert zero_star[1].status is ChallengeStatus.LOCKED

    completed = service.evaluate_path(
        CONTROL_CHALLENGES,
        (progress("exact-output", 1),),
    )
    assert completed[0].status is ChallengeStatus.COMPLETED
    assert completed[0].accessible is True
    assert completed[1].status is ChallengeStatus.AVAILABLE

    mastered = service.evaluate_path(
        CONTROL_CHALLENGES,
        (
            progress("exact-output", 3, 100),
            progress("output-restrictions", 1),
            progress("formatting-rules", 1),
            progress("multiple-constraints", 1),
        ),
    )
    assert mastered[0].status is ChallengeStatus.MASTERED
    assert mastered[4].status is ChallengeStatus.AVAILABLE


def test_control_path_has_versioned_deterministic_content() -> None:
    assert [item.challenge.order for item in CONTROL_CHALLENGES] == [1, 2, 3, 4, 5]
    assert [item.version.difficulty.value for item in CONTROL_CHALLENGES] == [
        "easy",
        "easy",
        "medium",
        "hard",
        "boss",
    ]
    assert all(item.version.version_id == "1" for item in CONTROL_CHALLENGES)
    assert all(len(item.version.visible_test_cases) == 3 for item in CONTROL_CHALLENGES)
    assert all(
        5 <= len(CONTROL_HIDDEN_TEST_SUITES[item.challenge.id].test_cases) <= 8
        for item in CONTROL_CHALLENGES
    )
    assert all(not hasattr(item.version, "hidden_test_cases") for item in CONTROL_CHALLENGES)
