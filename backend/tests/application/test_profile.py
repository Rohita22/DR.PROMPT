import asyncio
from datetime import UTC, datetime

from app.application.profile import GetCurrentUserProfileUseCase
from app.domains.auth import ApplicationUser, AuthProvider
from app.domains.profile import ProfileActivity, ProfileSnapshot


class FakeProfileReader:
    def __init__(self, snapshot: ProfileSnapshot) -> None:
        self.snapshot = snapshot
        self.calls: list[tuple[str, int]] = []

    async def get_snapshot(self, user_id: str, *, recent_limit: int) -> ProfileSnapshot:
        self.calls.append((user_id, recent_limit))
        return self.snapshot


def _user(username: str | None = None) -> ApplicationUser:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return ApplicationUser(
        id="fb59f126-4a52-4591-9e1b-866934a1fb31",
        auth_provider=AuthProvider.SUPABASE,
        auth_provider_user_id="private-provider-subject",
        email="private@example.com",
        username=username,
        created_at=now,
        updated_at=now,
    )


def test_profile_use_case_builds_safe_display_summary() -> None:
    activity = ProfileActivity(
        challenge_slug="formatting-rules",
        challenge_title="Formatting Rules",
        score=94.5,
        accuracy=100,
        stars=2,
        prompt_tokens=81,
        xp_earned=25,
        submitted_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    reader = FakeProfileReader(ProfileSnapshot(840, 5, 4, 10, 2, 7, (activity,)))

    result = asyncio.run(GetCurrentUserProfileUseCase(reader).execute(_user("PromptSmith")))

    assert result.player == "PromptSmith"
    assert result.level == 2
    assert result.level_progress.level_floor == 500
    assert result.level_progress.next_level_at == 1000
    assert result.level_progress.earned_in_level == 340
    assert result.total_stars == 15
    assert result.best_leaderboard_position == 7
    assert result.recent_activity[0].xp_earned == 25
    assert reader.calls == [("fb59f126-4a52-4591-9e1b-866934a1fb31", 5)]


def test_profile_uses_stable_privacy_safe_fallback_and_supports_zero_progress() -> None:
    reader = FakeProfileReader(ProfileSnapshot(0, 5, 0, 0, 0, None, ()))

    result = asyncio.run(GetCurrentUserProfileUseCase(reader).execute(_user()))

    assert result.player.startswith("Player-")
    assert result.level == 1
    assert result.challenges_completed == 0
    assert result.best_leaderboard_position is None
    assert result.recent_activity == ()
