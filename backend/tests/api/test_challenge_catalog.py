from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_challenge_detail_use_case,
    get_current_user,
    get_list_challenges_use_case,
    get_optional_current_user,
    get_submit_challenge_use_case,
)
from app.application.challenges import (
    ChallengeAccessService,
    GetChallengeDetailUseCase,
    ListChallengesUseCase,
)
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.domains.auth import ApplicationUser, AuthProvider
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionResult
from app.domains.scoring.service import ScoringService
from app.infrastructure.challenges import (
    InMemoryChallengeRepository,
    InMemoryHiddenTestRepository,
)
from app.infrastructure.submissions import InMemorySubmissionRepository
from app.main import app
from tests.fakes.llm import FakeLLMProvider
from tests.fakes.tokenization import FakePromptTokenCounter

USER = ApplicationUser(
    id="33333333-3333-4333-8333-333333333333",
    auth_provider=AuthProvider.SUPABASE,
    auth_provider_user_id="catalog-user",
    email=None,
    username=None,
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def catalog_dependencies():
    challenges = InMemoryChallengeRepository()
    progress = InMemorySubmissionRepository()
    access = ChallengeAccessService(challenges, progress)
    app.dependency_overrides[get_optional_current_user] = lambda: None
    app.dependency_overrides[get_list_challenges_use_case] = lambda: ListChallengesUseCase(access)
    app.dependency_overrides[get_challenge_detail_use_case] = lambda: GetChallengeDetailUseCase(
        challenges, access
    )
    return challenges, progress, access


def test_anonymous_catalog_is_ordered_with_only_first_available() -> None:
    catalog_dependencies()

    response = TestClient(app).get("/api/v1/challenges")

    assert response.status_code == 200
    challenges = response.json()["challenges"]
    assert [item["slug"] for item in challenges] == [
        "exact-output",
        "output-restrictions",
        "formatting-rules",
        "multiple-constraints",
        "control-boss",
    ]
    assert [item["status"] for item in challenges] == [
        "available",
        "locked",
        "locked",
        "locked",
        "locked",
    ]
    assert all("hidden" not in key for item in challenges for key in item)


def test_detail_exposes_safe_content_and_locked_access_is_predictable() -> None:
    catalog_dependencies()
    client = TestClient(app)

    first = client.get("/api/v1/challenges/exact-output")
    locked = client.get("/api/v1/challenges/output-restrictions")

    assert first.status_code == 200
    assert first.json()["title"] == "Exact Output"
    assert len(first.json()["examples"]) == 2
    assert {"hidden_tests", "evaluation_config", "model_config"}.isdisjoint(first.json())
    assert locked.status_code == 401
    assert locked.json()["error"]["code"] == "challenge_authentication_required"


def test_authenticated_locked_detail_returns_403() -> None:
    catalog_dependencies()
    app.dependency_overrides[get_optional_current_user] = lambda: USER

    response = TestClient(app).get("/api/v1/challenges/control-boss")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "challenge_locked"


def test_locked_submit_api_executes_and_persists_nothing() -> None:
    challenges = InMemoryChallengeRepository()
    progress = InMemorySubmissionRepository()
    provider = FakeLLMProvider(LLMExecutionResult(output_text="unused", model_id="fake"))
    use_case = SubmitChallengeUseCase(
        challenge_reader=challenges,
        hidden_test_suite_reader=InMemoryHiddenTestRepository(),
        llm_provider=provider,
        evaluation_engine=EvaluationEngine.with_builtin_graders(),
        prompt_token_counter=FakePromptTokenCounter(5),
        scoring_service=ScoringService(),
        submission_repository=progress,
        access_service=ChallengeAccessService(challenges, progress),
    )
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_submit_challenge_use_case] = lambda: use_case

    response = TestClient(app).post(
        "/api/v1/challenges/output-restrictions/submit",
        json={"prompt": "Return the final label only."},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "challenge_locked"
    assert provider.requests == []
    assert progress.submissions == []
    assert progress.progress == {}
    assert progress.xp_transactions == []
