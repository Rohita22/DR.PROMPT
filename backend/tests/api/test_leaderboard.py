from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_challenge_leaderboard_use_case,
    get_optional_current_user,
)
from app.application.leaderboard import GetChallengeLeaderboardUseCase
from app.domains.auth import ApplicationUser, AuthProvider
from app.domains.leaderboard import LeaderboardPage, RankedLeaderboardSubmission
from app.infrastructure.challenges import InMemoryChallengeRepository
from app.main import app

CURRENT_USER = ApplicationUser(
    id="33333333-3333-4333-8333-333333333333",
    auth_provider=AuthProvider.SUPABASE,
    auth_provider_user_id="private-provider-id",
    email="private@example.com",
    username=None,
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
)


class StaticLeaderboardReader:
    async def get_page(self, **arguments: object) -> LeaderboardPage:
        current_user_id = arguments["current_user_id"]
        current = _entry(18, str(current_user_id), None) if current_user_id is not None else None
        return LeaderboardPage((_entry(1, "other-user", "aiwizard"),), 18, current)


def _entry(rank: int, user_id: str, username: str | None) -> RankedLeaderboardSubmission:
    return RankedLeaderboardSubmission(
        rank=rank,
        submission_id=f"submission-{rank}",
        user_id=user_id,
        username=username,
        score=98.4 if rank == 1 else 91.4,
        accuracy=100 if rank == 1 else 90,
        prompt_tokens=52 if rank == 1 else 71,
        stars=3 if rank == 1 else 2,
        submitted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def _override_leaderboard() -> None:
    app.dependency_overrides[get_challenge_leaderboard_use_case] = lambda: (
        GetChallengeLeaderboardUseCase(
            InMemoryChallengeRepository(),
            StaticLeaderboardReader(),
        )
    )


def test_public_leaderboard_is_paginated_and_privacy_safe() -> None:
    _override_leaderboard()
    app.dependency_overrides[get_optional_current_user] = lambda: None

    response = TestClient(app).get("/api/v1/challenges/control-boss/leaderboard")

    assert response.status_code == 200
    body = response.json()
    assert body["challenge"] == "control-boss"
    assert body["version"] == "1"
    assert body["limit"] == 25
    assert body["offset"] == 0
    assert body["total_entries"] == 18
    assert body["has_more"] is True
    assert body["current_user_entry"] is None
    assert body["entries"][0]["player"] == "aiwizard"
    assert {
        "email",
        "user_id",
        "auth_provider_user_id",
        "prompt",
        "hidden_tests",
        "expected",
        "actual",
        "model_identifier",
    }.isdisjoint(body["entries"][0])


def test_authenticated_user_receives_position_outside_current_page() -> None:
    _override_leaderboard()
    app.dependency_overrides[get_optional_current_user] = lambda: CURRENT_USER

    response = TestClient(app).get("/api/v1/challenges/exact-output/leaderboard?limit=1&offset=0")

    assert response.status_code == 200
    current = response.json()["current_user_entry"]
    assert current["rank"] == 18
    assert current["is_current_user"] is True
    assert current["player"].startswith("Player-")
    assert CURRENT_USER.id not in current["player"]
    assert CURRENT_USER.email not in response.text
    assert CURRENT_USER.auth_provider_user_id not in response.text


def test_unknown_challenge_and_invalid_pagination_are_rejected() -> None:
    _override_leaderboard()
    app.dependency_overrides[get_optional_current_user] = lambda: None
    client = TestClient(app)

    assert client.get("/api/v1/challenges/missing/leaderboard").status_code == 404
    assert client.get("/api/v1/challenges/exact-output/leaderboard?limit=101").status_code == 422
    assert client.get("/api/v1/challenges/exact-output/leaderboard?offset=-1").status_code == 422
