import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_challenge_detail_use_case,
    get_current_user,
    get_run_challenge_use_case,
    get_starter_preview_use_case,
    get_submit_challenge_use_case,
)
from app.api.schemas.challenges import (
    ApplicationRunResponse,
    ApplicationSubmitResponse,
    ChallengeListItemResponse,
)
from app.application.challenges.catalog import GetChallengeDetailUseCase, GetStarterPreviewUseCase
from app.application.challenges.run_challenge import RunChallengeUseCase
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.domains.auth import ApplicationUser, AuthProvider
from app.domains.challenges.models import ChallengeType
from app.domains.execution import ChallengeExecutorResolver
from app.domains.execution.application import ApplicationChallengeExecutor
from app.domains.progression import ChallengeAccess, ChallengeStatus
from app.domains.scoring.service import ScoringService
from app.infrastructure.application import LocalWorkspaceFactory, StarterProjectRepository
from app.infrastructure.challenges.application_fixtures import (
    RESPONSIVE_HERO_CHALLENGE,
    RESPONSIVE_HERO_CONFIG,
)
from app.infrastructure.challenges.in_memory_repository import InMemoryChallengeRepository
from app.infrastructure.submissions import InMemorySubmissionRepository
from app.main import app
from tests.fakes.application import FakeCodingAgent, FakeEvaluator, solution_output
from tests.fakes.tokenization import FakePromptTokenCounter

USER = ApplicationUser(
    id="5a0e4d0e-5ad9-4bcb-8a5e-3a4f10d1a0c2",
    auth_provider=AuthProvider.SUPABASE,
    auth_provider_user_id="supabase-application-player",
    email="builder@example.com",
    username=None,
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
)
HIDDEN_ONLY = set(RESPONSIVE_HERO_CONFIG.hidden_checks) - set(RESPONSIVE_HERO_CONFIG.visible_checks)


class AllowAllAccess:
    async def require_access(self, playable, _owner_user_id) -> ChallengeAccess:
        return ChallengeAccess(playable, ChallengeStatus.AVAILABLE, None, 0, 0)


@pytest.fixture
def overrides(tmp_path: Path):
    reader = InMemoryChallengeRepository((RESPONSIVE_HERO_CHALLENGE,))
    resolver = ChallengeExecutorResolver(
        {
            ChallengeType.APPLICATION: ApplicationChallengeExecutor(
                FakeCodingAgent(solution_output()),
                LocalWorkspaceFactory(StarterProjectRepository(), temp_root=tmp_path),
                FakeEvaluator(),
                StarterProjectRepository(),
            )
        }
    )
    submissions = InMemorySubmissionRepository({"control-responsive-hero": "responsive-hero"})
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_run_challenge_use_case] = lambda: RunChallengeUseCase(
        reader, resolver, AllowAllAccess()
    )
    app.dependency_overrides[get_submit_challenge_use_case] = lambda: SubmitChallengeUseCase(
        challenge_reader=reader,
        executor_resolver=resolver,
        prompt_token_counter=FakePromptTokenCounter(60),
        scoring_service=ScoringService(),
        submission_repository=submissions,
        access_service=AllowAllAccess(),
    )
    app.dependency_overrides[get_challenge_detail_use_case] = lambda: GetChallengeDetailUseCase(
        reader, AllowAllAccess()
    )
    app.dependency_overrides[get_starter_preview_use_case] = lambda: GetStarterPreviewUseCase(
        reader, StarterProjectRepository()
    )
    yield submissions
    app.dependency_overrides.clear()


def test_run_returns_application_feedback_with_screenshots_and_visible_checks_only(
    overrides,
) -> None:
    response = TestClient(app).post(
        "/api/v1/challenges/responsive-hero/run", json={"prompt": "Make the hero responsive."}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["challenge_type"] == "application"
    assert (payload["passed"], payload["total"], payload["evaluation_score"]) == (4, 4, 100.0)
    assert "accuracy" not in payload
    assert [c["id"] for c in payload["checks"]] == list(RESPONSIVE_HERO_CONFIG.visible_checks)
    assert payload["checks"][1]["label"] == "Desktop hero uses two columns, content on the left"
    assert payload["agent"] == {"status": "applied", "message": None}
    assert payload["changed_files"][0]["path"] == "src/styles.css"
    assert payload["build"]["status"] == "passed"
    assert [s["viewport"] for s in payload["screenshots"]] == ["desktop", "mobile"]
    assert payload["screenshots"][0]["image"].startswith("data:image/png;base64,")
    serialized = json.dumps(payload)
    assert not any(check_id in serialized for check_id in HIDDEN_ONLY)
    assert "\\\\" not in serialized and "drprompt-app-" not in serialized


def test_submit_returns_aggregates_without_hidden_check_details(overrides) -> None:
    response = TestClient(app).post(
        "/api/v1/challenges/responsive-hero/submit",
        json={"prompt": "Make the hero responsive."},
        headers={"Idempotency-Key": "submit-action-123"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["challenge_type"] == "application"
    assert (payload["passed"], payload["total"]) == (9, 9)
    assert (payload["evaluation_score"], payload["score"], payload["stars"]) == (100.0, 100.0, 3)
    assert payload["xp_earned"] == 175 and payload["completed"] is True
    assert payload["screenshot"]["viewport"] == "desktop"
    assert payload["screenshot"]["label"] == "desktop"
    assert set(payload) == set(ApplicationSubmitResponse.model_fields)
    serialized = json.dumps(payload)
    for hidden in (*RESPONSIVE_HERO_CONFIG.hidden_checks, "checks", "log"):
        assert f'"{hidden}"' not in serialized
    assert overrides.submissions[0].accuracy == 100.0


def test_detail_exposes_only_public_application_facts(overrides) -> None:
    payload = TestClient(app).get("/api/v1/challenges/responsive-hero").json()
    assert payload["challenge_type"] == "application"
    assert payload["application"] == {
        "editable_files": ["src/index.html", "src/styles.css"],
        "starter_preview_viewports": ["desktop", "mobile"],
        "execution_mode": "static",
        "available": True,
    }
    serialized = json.dumps(payload)
    for private in (*RESPONSIVE_HERO_CONFIG.hidden_checks, "build.mjs", "build_command", "limits"):
        assert private not in serialized


def test_starter_preview_is_served_as_png_and_unknown_viewports_are_404(overrides) -> None:
    client = TestClient(app)
    response = client.get("/api/v1/challenges/responsive-hero/starter-preview/desktop.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    assert (
        client.get("/api/v1/challenges/responsive-hero/starter-preview/wide.png").status_code == 404
    )


def test_application_response_schemas_cannot_represent_hidden_detail() -> None:
    assert "checks" not in ApplicationSubmitResponse.model_fields
    assert "screenshots" in ApplicationRunResponse.model_fields
    assert "challenge_type" in ChallengeListItemResponse.model_fields
