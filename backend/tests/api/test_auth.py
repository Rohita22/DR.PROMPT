from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_access_token_verifier,
    get_current_user,
    get_user_progress_use_case,
    get_user_repository,
)
from app.application.progression import GetUserProgressUseCase
from app.core.exceptions import AuthenticationError, AuthenticationServiceError
from app.domains.auth import (
    ApplicationUser,
    AuthenticatedIdentity,
    AuthProvider,
)
from app.domains.progression import UserProgressItem, UserProgressSummary
from app.infrastructure.auth import InMemoryUserRepository
from app.main import app


class FakeVerifier:
    def __init__(self, identity: AuthenticatedIdentity | None) -> None:
        self.identity = identity
        self.tokens: list[str] = []

    async def verify(self, access_token: str) -> AuthenticatedIdentity:
        self.tokens.append(access_token)
        if self.identity is None:
            raise AuthenticationError()
        return self.identity


class UnavailableVerifier:
    async def verify(self, access_token: str) -> AuthenticatedIdentity:
        raise AuthenticationServiceError()


class FakeProgressReader:
    async def get_summary(self, user_id: str) -> UserProgressSummary:
        assert user_id == "fb59f126-4a52-4591-9e1b-866934a1fb31"
        return UserProgressSummary(
            total_xp=175,
            challenges_completed=1,
            stars_earned=3,
            challenges=(
                UserProgressItem(
                    challenge_slug="exact-output",
                    best_score=100,
                    best_stars=3,
                    attempts=4,
                    completed_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            ),
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def test_me_requires_bearer_authentication() -> None:
    response = TestClient(app).get("/api/v1/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "authentication_error"


def test_me_verifies_token_synchronizes_user_and_returns_safe_fields() -> None:
    identity = AuthenticatedIdentity(
        AuthProvider.SUPABASE,
        "provider-user-1",
        "player@example.com",
    )
    verifier = FakeVerifier(identity)
    users = InMemoryUserRepository()
    app.dependency_overrides[get_access_token_verifier] = lambda: verifier
    app.dependency_overrides[get_user_repository] = lambda: users

    response = TestClient(app).get(
        "/api/v1/me",
        headers={"Authorization": "Bearer signed-access-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": users.users[0].id,
        "email": "player@example.com",
        "username": None,
    }
    assert verifier.tokens == ["signed-access-token"]
    assert set(response.json()) == {"id", "email", "username"}


def test_invalid_token_returns_safe_401() -> None:
    verifier = FakeVerifier(None)
    app.dependency_overrides[get_access_token_verifier] = lambda: verifier
    app.dependency_overrides[get_user_repository] = InMemoryUserRepository

    response = TestClient(app).get(
        "/api/v1/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "authentication_error",
            "message": "Valid bearer authentication is required.",
        }
    }


def test_verification_infrastructure_failure_returns_safe_503() -> None:
    app.dependency_overrides[get_access_token_verifier] = UnavailableVerifier
    app.dependency_overrides[get_user_repository] = InMemoryUserRepository

    response = TestClient(app).get(
        "/api/v1/me",
        headers={"Authorization": "Bearer opaque-token"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "authentication_service_error",
            "message": "Authentication verification is unavailable.",
        }
    }
    assert "opaque-token" not in response.text


def test_me_schema_does_not_expose_provider_identity_or_tokens() -> None:
    now = datetime.now(UTC)
    user = ApplicationUser(
        id="fb59f126-4a52-4591-9e1b-866934a1fb31",
        auth_provider=AuthProvider.SUPABASE,
        auth_provider_user_id="private-provider-id",
        email=None,
        username=None,
        created_at=now,
        updated_at=now,
    )
    app.dependency_overrides[get_current_user] = lambda: user

    payload = TestClient(app).get("/api/v1/me").json()

    assert payload == {"id": user.id, "email": None, "username": None}


def test_me_progress_requires_authentication() -> None:
    response = TestClient(app).get("/api/v1/me/progress")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_progress_returns_only_current_user_aggregates() -> None:
    now = datetime.now(UTC)
    user = ApplicationUser(
        id="fb59f126-4a52-4591-9e1b-866934a1fb31",
        auth_provider=AuthProvider.SUPABASE,
        auth_provider_user_id="private-provider-id",
        email=None,
        username=None,
        created_at=now,
        updated_at=now,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_user_progress_use_case] = lambda: GetUserProgressUseCase(
        FakeProgressReader()
    )

    response = TestClient(app).get("/api/v1/me/progress")

    assert response.status_code == 200
    assert response.json() == {
        "total_xp": 175,
        "challenges_completed": 1,
        "stars_earned": 3,
        "challenges": [
            {
                "challenge": "exact-output",
                "best_score": 100.0,
                "best_stars": 3,
                "attempts": 4,
                "completed": True,
                "completed_at": "2026-01-01T00:00:00Z",
            }
        ],
    }
    assert {"user_id", "submission_id", "xp_transactions"}.isdisjoint(response.json())
