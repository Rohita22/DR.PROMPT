from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_access_token_verifier,
    get_current_user,
    get_submit_challenge_use_case,
    get_user_repository,
)
from app.api.schemas.challenges import (
    RunChallengeResponse,
    SubmitChallengeResponse,
    VisibleTestRunResponse,
)
from app.application.challenges.access import ChallengeAccessService
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.core.exceptions import AuthenticationError, LLMRateLimitError, PersistenceError
from app.domains.auth import ApplicationUser, AuthenticatedIdentity, AuthProvider
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionRequest, LLMExecutionResult
from app.domains.scoring.service import ScoringService
from app.infrastructure.auth import InMemoryUserRepository
from app.infrastructure.challenges import (
    InMemoryChallengeRepository,
    InMemoryHiddenTestRepository,
)
from app.infrastructure.submissions import InMemorySubmissionRepository
from app.main import app
from tests.fakes.llm import FakeLLMProvider
from tests.fakes.tokenization import FakePromptTokenCounter

TEST_USER = ApplicationUser(
    id="2fbb08d8-bffc-4b2b-bc2f-3b6e87721dc1",
    auth_provider=AuthProvider.SUPABASE,
    auth_provider_user_id="supabase-user-1",
    email="player@example.com",
    username=None,
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
)


class RateLimitedProvider:
    async def generate(self, request: LLMExecutionRequest) -> LLMExecutionResult:
        del request
        raise LLMRateLimitError()


class RejectingTokenVerifier:
    async def verify(self, access_token: str) -> AuthenticatedIdentity:
        del access_token
        raise AuthenticationError()


class AcceptingTokenVerifier:
    async def verify(self, access_token: str) -> AuthenticatedIdentity:
        assert access_token == "valid-token"
        return AuthenticatedIdentity(
            AuthProvider.SUPABASE,
            "provider-user-for-submit",
            "owner@example.com",
        )


def make_submit_use_case(
    provider: FakeLLMProvider | RateLimitedProvider,
    hidden_repository: InMemoryHiddenTestRepository | None = None,
    token_count: int = 42,
    submission_repository: InMemorySubmissionRepository | None = None,
) -> SubmitChallengeUseCase:
    challenge_reader = InMemoryChallengeRepository()
    progression_repository = submission_repository or InMemorySubmissionRepository()
    return SubmitChallengeUseCase(
        challenge_reader=challenge_reader,
        hidden_test_suite_reader=(
            hidden_repository if hidden_repository is not None else InMemoryHiddenTestRepository()
        ),
        llm_provider=provider,
        evaluation_engine=EvaluationEngine.with_builtin_graders(),
        prompt_token_counter=FakePromptTokenCounter(token_count),
        scoring_service=ScoringService(),
        submission_repository=progression_repository,
        access_service=ChallengeAccessService(challenge_reader, progression_repository),
    )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.clear()


def test_submit_endpoint_returns_only_aggregate_hidden_evaluation() -> None:
    provider = FakeLLMProvider(
        LLMExecutionResult(output_text="YES", model_id="fake"),
        LLMExecutionResult(output_text="NO", model_id="fake"),
        LLMExecutionResult(output_text="NO", model_id="fake"),
        LLMExecutionResult(output_text="YES", model_id="fake"),
        LLMExecutionResult(output_text="NO", model_id="fake"),
        LLMExecutionResult(output_text="YES", model_id="fake"),
    )
    submissions = InMemorySubmissionRepository()
    app.dependency_overrides[get_submit_challenge_use_case] = lambda: make_submit_use_case(
        provider,
        submission_repository=submissions,
    )

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/submit",
        json={"prompt": "Return exactly YES if available, otherwise exactly NO."},
    )

    assert response.status_code == 200
    assert response.json() == {
        "challenge": "exact-output",
        "version": "1",
        "passed": 4,
        "total": 6,
        "accuracy": 66.67,
        "prompt_tokens": 42,
        "efficiency": 100.0,
        "score": 73.33,
        "stars": 0,
        "xp_earned": 0,
        "total_xp": 0,
        "best_score": 73.33,
        "best_stars": 0,
        "completed": False,
    }
    assert set(SubmitChallengeResponse.model_fields) == {
        "challenge",
        "version",
        "passed",
        "total",
        "accuracy",
        "prompt_tokens",
        "efficiency",
        "score",
        "stars",
        "xp_earned",
        "total_xp",
        "best_score",
        "best_stars",
        "completed",
    }
    assert submissions.submissions[0].user_id == TEST_USER.id


def test_run_and_submit_response_types_enforce_different_disclosure_boundaries() -> None:
    assert "tests" in RunChallengeResponse.model_fields
    assert {"input", "expected", "actual"}.issubset(VisibleTestRunResponse.model_fields)
    assert "tests" not in SubmitChallengeResponse.model_fields
    assert {"input", "expected", "actual", "id", "provider", "model"}.isdisjoint(
        SubmitChallengeResponse.model_fields
    )


def test_submit_endpoint_rejects_over_limit_prompt_before_provider_execution() -> None:
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))
    app.dependency_overrides[get_submit_challenge_use_case] = lambda: make_submit_use_case(
        provider,
        token_count=301,
    )

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/submit",
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "prompt_too_long",
            "message": "Prompt contains 301 tokens; maximum allowed is 300.",
        }
    }
    assert provider.requests == []


def test_submit_endpoint_returns_safe_error_when_hidden_suite_is_missing() -> None:
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))
    app.dependency_overrides[get_submit_challenge_use_case] = lambda: make_submit_use_case(
        provider,
        InMemoryHiddenTestRepository(suites=()),
    )

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/submit",
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "hidden_evaluation_unavailable",
            "message": "Challenge evaluation is unavailable.",
        }
    }
    assert provider.requests == []


def test_submit_provider_failure_remains_an_execution_error() -> None:
    app.dependency_overrides[get_submit_challenge_use_case] = lambda: make_submit_use_case(
        RateLimitedProvider()
    )

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/submit",
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "llm_rate_limit_error",
            "message": "The model provider rate limit was reached.",
        }
    }


class PersistenceFailingUseCase:
    async def execute(self, command: object) -> None:
        del command
        raise PersistenceError("Database operation failed.")


def test_submit_endpoint_sanitizes_persistence_errors() -> None:
    app.dependency_overrides[get_submit_challenge_use_case] = PersistenceFailingUseCase

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/submit",
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "persistence_error",
            "message": "Database operation failed.",
        }
    }


def test_submit_requires_bearer_authentication() -> None:
    app.dependency_overrides.pop(get_current_user)

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/submit",
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "authentication_error"


def test_submit_request_cannot_supply_ownership_or_progression_values() -> None:
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))
    app.dependency_overrides[get_submit_challenge_use_case] = lambda: make_submit_use_case(provider)

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/submit",
        json={
            "prompt": "Return YES or NO.",
            "user_id": "attacker-controlled-id",
            "xp_earned": 999999,
            "score": 100,
            "stars": 3,
            "attempts": 999,
        },
    )

    assert response.status_code == 422
    assert provider.requests == []


def test_authentication_failure_executes_and_persists_nothing() -> None:
    app.dependency_overrides.pop(get_current_user)
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))
    submissions = InMemorySubmissionRepository()
    app.dependency_overrides[get_access_token_verifier] = RejectingTokenVerifier
    app.dependency_overrides[get_user_repository] = InMemoryUserRepository
    app.dependency_overrides[get_submit_challenge_use_case] = lambda: make_submit_use_case(
        provider,
        submission_repository=submissions,
    )

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/submit",
        headers={"Authorization": "Bearer invalid-token"},
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 401
    assert provider.requests == []
    assert submissions.submissions == []


def test_verified_identity_owns_successful_submission() -> None:
    app.dependency_overrides.pop(get_current_user)
    users = InMemoryUserRepository()
    submissions = InMemorySubmissionRepository()
    provider = FakeLLMProvider(
        *(
            LLMExecutionResult(output_text=value, model_id="fake")
            for value in ("YES", "NO", "YES", "YES", "NO", "NO")
        )
    )
    app.dependency_overrides[get_access_token_verifier] = AcceptingTokenVerifier
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_submit_challenge_use_case] = lambda: make_submit_use_case(
        provider,
        submission_repository=submissions,
    )

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/submit",
        headers={"Authorization": "Bearer valid-token"},
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 200
    assert len(users.users) == 1
    assert submissions.submissions[0].user_id == users.users[0].id
