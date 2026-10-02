"""APPLICATION builder lifecycle and isolated admin testing."""

import asyncio
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.dependencies import (
    get_settings,
)
from app.api.schemas.admin import (
    AdminChallengeDetailResponse,
    ApplicationAuthoringInput,
    UpsertChallengeRequest,
)
from app.api.schemas.admin import TestChallengeResponse as AdminTestResponse
from app.application.admin.errors import AdminChallengeStateError
from app.application.admin.models import (
    CreateChallengeCommand,
    UpdateChallengeDraftCommand,
    VersionMetadata,
)
from app.application.admin.use_cases import (
    CreateChallengeUseCase,
    CreateChallengeVersionUseCase,
    PublishChallengeUseCase,
    UnpublishChallengeUseCase,
    UpdateChallengeDraftUseCase,
)
from app.application.admin.use_cases import TestChallengeUseCase as AdminTestUseCase
from app.domains.challenges.models import ChallengeType, PublicationState
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionResult
from app.domains.execution.application import ApplicationChallengeExecutor
from app.domains.scoring.service import ScoringService
from app.infrastructure.application import LocalWorkspaceFactory, StarterProjectRepository
from app.main import app
from tests.application.test_admin import MemoryAdminRepository, definition
from tests.fakes.application import FakeCodingAgent, FakeEvaluator, solution_output
from tests.fakes.llm import FakeLLMProvider
from tests.fakes.tokenization import FakePromptTokenCounter


def application_spec(package="responsive-hero"):
    config = StarterProjectRepository().load(package).defaults
    return replace(
        definition(with_tests=False),
        challenge_type=ChallengeType.APPLICATION,
        application=ApplicationAuthoringInput.from_config(config).to_spec(),
    )


def test_application_create_update_publish_version_unpublish():
    async def exercise():
        packages, repository = StarterProjectRepository(), MemoryAdminRepository()
        spec = application_spec("pricing-grid")
        await CreateChallengeUseCase(repository, packages).execute(CreateChallengeCommand(spec))
        assert repository.record.version.application_config.starter_project == "pricing-grid"
        assert repository.record.version.visible_test_cases == ()
        spec = replace(
            spec, application=replace(spec.application, editable_files=("src/styles.css",))
        )
        await UpdateChallengeDraftUseCase(repository, packages).execute(
            UpdateChallengeDraftCommand(spec.slug, spec)
        )
        assert repository.record.version.application_config.editable_files == ("src/styles.css",)
        await PublishChallengeUseCase(repository, packages).execute(spec.slug)
        with pytest.raises(AdminChallengeStateError):
            await UpdateChallengeDraftUseCase(repository, packages).execute(
                UpdateChallengeDraftCommand(spec.slug, spec)
            )
        repository.record = replace(
            repository.record,
            versions=(
                VersionMetadata("1", PublicationState.PUBLISHED, repository.record.created_at),
            ),
        )
        await CreateChallengeVersionUseCase(repository).execute(spec.slug)
        assert repository.record.version.version_id == "2"
        assert repository.record.version.challenge_type is ChallengeType.APPLICATION
        assert repository.record.version.application_config.editable_files == ("src/styles.css",)
        await PublishChallengeUseCase(repository, packages).execute(spec.slug)
        await UnpublishChallengeUseCase(repository).execute(spec.slug)
        assert repository.record.challenge.current_version_id is None

    asyncio.run(exercise())


def test_challenge_type_cannot_change_after_creation():
    async def exercise():
        repository = MemoryAdminRepository()
        await CreateChallengeUseCase(repository).execute(CreateChallengeCommand(definition()))
        with pytest.raises(AdminChallengeStateError, match="type cannot change"):
            await UpdateChallengeDraftUseCase(repository, StarterProjectRepository()).execute(
                UpdateChallengeDraftCommand("admin-test", application_spec())
            )

    asyncio.run(exercise())


def test_admin_test_uses_one_agent_call_and_exposes_private_checks_without_gameplay_writes(
    tmp_path,
):
    async def exercise():
        packages, repository = StarterProjectRepository(), MemoryAdminRepository()
        await CreateChallengeUseCase(repository, packages).execute(
            CreateChallengeCommand(application_spec())
        )
        before = repository.record
        provider = FakeLLMProvider(LLMExecutionResult("unused", "fake"))
        agent = FakeCodingAgent(solution_output())
        executor = ApplicationChallengeExecutor(
            agent, LocalWorkspaceFactory(packages, tmp_path), FakeEvaluator(), packages
        )
        use_case = AdminTestUseCase(
            repository,
            provider,
            EvaluationEngine.with_builtin_graders(),
            FakePromptTokenCounter(42),
            ScoringService(),
            executor,
        )
        result = await use_case.execute("admin-test", "Arrange the page.")
        response = AdminTestResponse.from_result(result)
        assert result.accuracy == 100
        assert len(agent.tasks) == 1 and provider.requests == []
        assert response.application is not None and len(response.application.screenshots) == 2
        assert len(response.hidden_checks) == 9
        assert all(c.label != "hidden" for c in response.hidden_checks)
        assert repository.record is before and repository.created == 1
        assert (
            not {"xp_earned", "total_xp", "completed", "best_score"} & response.model_dump().keys()
        )
        assert list(tmp_path.iterdir()) == []

    asyncio.run(exercise())


def test_admin_catalog_is_protected_and_contains_only_authoring_metadata():
    app.dependency_overrides[get_settings] = lambda: type(
        "SettingsStub",
        (),
        {"admin_api_key": type("Secret", (), {"get_secret_value": lambda self: "correct"})()},
    )()
    try:
        client = TestClient(app)
        assert client.get("/api/v1/admin/application-packages").status_code == 401
        response = client.get(
            "/api/v1/admin/application-packages", headers={"X-Admin-Key": "correct"}
        )
        assert response.status_code == 200
        assert [p["id"] for p in response.json()] == [
            "responsive-hero",
            "pricing-grid",
            "broken-signup-validation",
            "product-filter",
        ]
        assert (
            "C:\\" not in response.text
            and "def " not in response.text
            and "selectors" not in response.text
        )
        assert all(p["visible_checks"] and p["hidden_checks"] for p in response.json())
    finally:
        app.dependency_overrides.clear()


def test_application_api_roundtrip_and_rejection_of_executable_fields():
    from app.application.admin.use_cases import build_record

    packages = StarterProjectRepository()
    spec = application_spec()
    config = packages.load(spec.application.package_id).defaults
    record = build_record(
        spec,
        challenge_id="control-admin-test",
        current_version=None,
        publication_state=PublicationState.DRAFT,
        application_config=config,
    )
    data = AdminChallengeDetailResponse.from_record(record).model_dump(mode="json")
    for key in ("id", "current_version", "versions", "created_at", "updated_at"):
        data.pop(key)
    assert UpsertChallengeRequest.model_validate(data).to_spec().application == spec.application
    for extra in ("source_code", "build_command", "python", "shell"):
        with pytest.raises(ValidationError):
            UpsertChallengeRequest.model_validate(
                {**data, "application": {**data["application"], extra: "malicious"}}
            )
    with pytest.raises(ValidationError):
        UpsertChallengeRequest.model_validate({**data, "challenge_type": "image"})
