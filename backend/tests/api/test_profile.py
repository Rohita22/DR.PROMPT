from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_current_user_profile_use_case
from app.application.profile import GetCurrentUserProfileUseCase
from app.domains.auth import ApplicationUser, AuthProvider
from app.domains.profile import ProfileActivity, ProfileSnapshot
from app.main import app


class FakeProfileReader:
    def __init__(self) -> None:
        self.user_ids: list[str] = []

    async def get_snapshot(self, user_id: str, *, recent_limit: int) -> ProfileSnapshot:
        self.user_ids.append(user_id)
        assert recent_limit == 5
        return ProfileSnapshot(
            total_xp=840,
            published_challenges=5,
            challenges_completed=4,
            stars_earned=10,
            three_star_completions=2,
            best_leaderboard_rank=7,
            recent_activity=(
                ProfileActivity(
                    challenge_slug="formatting-rules",
                    challenge_title="Formatting Rules",
                    score=94.5,
                    accuracy=100,
                    stars=2,
                    prompt_tokens=81,
                    xp_earned=25,
                    submitted_at=datetime(2026, 1, 2, tzinfo=UTC),
                ),
            ),
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def _current_user() -> ApplicationUser:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return ApplicationUser(
        id="fb59f126-4a52-4591-9e1b-866934a1fb31",
        auth_provider=AuthProvider.SUPABASE,
        auth_provider_user_id="private-provider-subject",
        email="private@example.com",
        username=None,
        created_at=now,
        updated_at=now,
    )


def test_profile_requires_authentication() -> None:
    response = TestClient(app).get("/api/v1/me/profile")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_profile_returns_current_user_safe_aggregates_only() -> None:
    reader = FakeProfileReader()
    user = _current_user()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_profile_use_case] = lambda: (
        GetCurrentUserProfileUseCase(reader)
    )

    response = TestClient(app).get("/api/v1/me/profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["player"].startswith("Player-")
    assert payload["level"] == 2
    assert payload["level_progress"] == {
        "level_floor": 500,
        "next_level_at": 1000,
        "earned_in_level": 340,
        "required_in_level": 500,
    }
    assert payload["challenges"] == {"completed": 4, "total": 5}
    assert payload["stars"] == {"earned": 10, "total": 15}
    assert payload["three_star_completions"] == 2
    assert payload["best_leaderboard_position"] == 7
    assert payload["recent_activity"][0] == {
        "challenge": "formatting-rules",
        "title": "Formatting Rules",
        "score": 94.5,
        "accuracy": 100.0,
        "stars": 2,
        "prompt_tokens": 81,
        "xp_earned": 25,
        "submitted_at": "2026-01-02T00:00:00Z",
    }
    assert reader.user_ids == [user.id]
    private_fields = {
        "id",
        "user_id",
        "email",
        "auth_provider",
        "auth_provider_user_id",
        "prompt",
        "hidden_tests",
        "model_identifier",
    }
    assert private_fields.isdisjoint(payload)
    assert private_fields.isdisjoint(payload["recent_activity"][0])
