from datetime import UTC, datetime

import pytest

from app.core.exceptions import DomainError
from app.domains.profile import (
    LevelConfiguration,
    ProfileActivity,
    ProfileSnapshot,
    calculate_level,
)


@pytest.mark.parametrize(
    ("total_xp", "expected_level", "floor", "next_at", "earned"),
    [
        (0, 1, 0, 500, 0),
        (499, 1, 0, 500, 499),
        (500, 2, 500, 1000, 0),
        (999, 2, 500, 1000, 499),
        (1000, 3, 1000, 1500, 0),
    ],
)
def test_level_boundaries(
    total_xp: int,
    expected_level: int,
    floor: int,
    next_at: int,
    earned: int,
) -> None:
    result = calculate_level(total_xp)

    assert result.level == expected_level
    assert result.level_floor == floor
    assert result.next_level_at == next_at
    assert result.earned_in_level == earned
    assert result.required_in_level == 500


def test_level_configuration_is_customizable_and_validated() -> None:
    assert calculate_level(200, LevelConfiguration(xp_per_level=100)).level == 3

    with pytest.raises(DomainError):
        LevelConfiguration(xp_per_level=0)
    with pytest.raises(DomainError):
        calculate_level(-1)


def test_profile_snapshot_enforces_aggregate_invariants() -> None:
    activity = ProfileActivity(
        challenge_slug="exact-output",
        challenge_title="Exact Output",
        score=98.5,
        accuracy=100,
        stars=3,
        prompt_tokens=42,
        xp_earned=175,
        submitted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    snapshot = ProfileSnapshot(175, 5, 1, 3, 1, 7, (activity,))

    assert snapshot.recent_activity == (activity,)
    with pytest.raises(DomainError):
        ProfileSnapshot(0, 1, 2, 0, 0, None, ())
