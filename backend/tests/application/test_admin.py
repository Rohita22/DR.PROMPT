import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from functools import wraps

import pytest

from app.application.admin.errors import AdminChallengeStateError
from app.application.admin.models import (
    ChallengeAuthoringSpec,
    CreateChallengeCommand,
    EfficiencyTierAuthoringSpec,
    GraderAuthoringSpec,
    ModelAuthoringSpec,
    ScoringAuthoringSpec,
    UpdateChallengeDraftCommand,
    VersionMetadata,
)
from app.application.admin.models import (
    TestCaseAuthoringSpec as AuthoringTestSpec,
)
from app.application.admin.use_cases import (
    CreateChallengeUseCase,
    CreateChallengeVersionUseCase,
    PublishChallengeUseCase,
    UnpublishChallengeUseCase,
    UpdateChallengeDraftUseCase,
)
from app.application.admin.use_cases import (
    TestChallengeUseCase as AdminTestUseCase,
)
from app.domains.challenges.models import (
    ChallengeTrack,
    ChallengeType,
    Difficulty,
    PublicationState,
)
from app.domains.evaluation.configuration import GraderType
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionResult
from app.domains.scoring.service import ScoringService
from tests.fakes.llm import FakeLLMProvider
from tests.fakes.tokenization import FakePromptTokenCounter


def async_test(function):
    @wraps(function)
    def run():
        return asyncio.run(function())

    return run


class MemoryAdminRepository:
    def __init__(self) -> None:
        self.record = None
        self.created = 0

    async def list_all(self):
        return ()

    async def get_by_slug(self, slug):
        return self.record if self.record and self.record.challenge.slug == slug else None

    async def create(self, record):
        self.record = record
        self.created += 1

    async def update_draft(self, record):
        self.record = record

    async def create_version(self, record):
        self.record = record

    async def publish(self, slug, version):
        assert self.record is not None and self.record.challenge.slug == slug
        published = replace(self.record.version, publication_state=PublicationState.PUBLISHED)
        challenge = replace(self.record.challenge, current_version_id=version)
        versions = tuple(
            replace(item, publication_state=PublicationState.PUBLISHED)
            if item.version == version
            else replace(item, publication_state=PublicationState.RETIRED)
            if item.publication_state is PublicationState.PUBLISHED
            else item
            for item in self.record.versions
        )
        self.record = replace(
            self.record,
            challenge=challenge,
            version=published,
            versions=versions,
        )
        return self.record

    async def unpublish(self, slug):
        assert self.record is not None and self.record.challenge.slug == slug
        self.record = replace(
            self.record,
            challenge=replace(self.record.challenge, current_version_id=None),
            version=replace(self.record.version, publication_state=PublicationState.RETIRED),
        )
        return self.record


def definition(*, with_tests: bool = True) -> ChallengeAuthoringSpec:
    grader = GraderAuthoringSpec(GraderType.EXACT_MATCH)
    visible = (AuthoringTestSpec("visible-1", "online", "YES", grader),) if with_tests else ()
    hidden = (AuthoringTestSpec("hidden-1", "offline", "NO", grader),) if with_tests else ()
    return ChallengeAuthoringSpec(
        slug="admin-test",
        track=ChallengeTrack.CONTROL,
        order=12,
        version="1",
        title="Admin Test",
        description="A challenge authored in tests.",
        objective="Return the exact status label.",
        constraints=("Return one label.",),
        difficulty=Difficulty.EASY,
        visible_examples=(),
        visible_test_cases=visible,
        hidden_test_cases=hidden,
        prompt_token_limit=100,
        default_grader=grader,
        scoring=ScoringAuthoringSpec(
            0.8,
            0.2,
            (EfficiencyTierAuthoringSpec(60, 100), EfficiencyTierAuthoringSpec(100, 80)),
            40,
            70,
            90,
            100,
            60,
        ),
        model=ModelAuthoringSpec("openai/gpt-oss-20b", 0, 16, "Apply the prompt."),
    )


@async_test
async def test_create_draft_then_publish_and_unpublish_preserves_lifecycle() -> None:
    repository = MemoryAdminRepository()
    created = await CreateChallengeUseCase(repository).execute(
        CreateChallengeCommand(definition(), publish=False)
    )
    assert created.publication_state is PublicationState.DRAFT
    assert repository.record.challenge.current_version_id is None

    published = await PublishChallengeUseCase(repository).execute("admin-test")
    assert published.publication_state is PublicationState.PUBLISHED
    assert repository.record.challenge.current_version_id == "1"

    unpublished = await UnpublishChallengeUseCase(repository).execute("admin-test")
    assert unpublished.publication_state is PublicationState.RETIRED
    assert repository.record.challenge.current_version_id is None


@async_test
async def test_publish_rejects_incomplete_draft() -> None:
    repository = MemoryAdminRepository()
    await CreateChallengeUseCase(repository).execute(
        CreateChallengeCommand(definition(with_tests=False))
    )
    with pytest.raises(AdminChallengeStateError):
        await PublishChallengeUseCase(repository).execute("admin-test")


@async_test
async def test_draft_update_rebuilds_validated_configuration() -> None:
    repository = MemoryAdminRepository()
    original = definition()
    await CreateChallengeUseCase(repository).execute(CreateChallengeCommand(original))
    changed = replace(
        original,
        title="Revised Admin Test",
        model=replace(original.model, temperature=0.4),
        scoring=replace(original.scoring, accuracy_weight=0.7, efficiency_weight=0.3),
    )
    result = await UpdateChallengeDraftUseCase(repository).execute(
        UpdateChallengeDraftCommand("admin-test", changed)
    )
    assert result.publication_state is PublicationState.DRAFT
    assert repository.record.version.title == "Revised Admin Test"
    assert repository.record.version.model_config.temperature == 0.4
    assert repository.record.version.scoring_config.accuracy_weight == 0.7


@async_test
async def test_new_version_clones_history_without_mutating_published_version() -> None:
    repository = MemoryAdminRepository()
    await CreateChallengeUseCase(repository).execute(CreateChallengeCommand(definition()))
    await PublishChallengeUseCase(repository).execute("admin-test")
    repository.record = replace(
        repository.record,
        versions=(VersionMetadata("1", PublicationState.PUBLISHED, datetime.now(UTC)),),
    )
    result = await CreateChallengeVersionUseCase(repository).execute("admin-test")
    assert result.version == "2"
    assert repository.record.version.publication_state is PublicationState.DRAFT
    assert repository.record.challenge.current_version_id == "1"
    assert repository.record.version.visible_test_cases[0].id == "visible-1"


@async_test
async def test_admin_test_executes_visible_and_hidden_without_submission_dependency() -> None:
    repository = MemoryAdminRepository()
    await CreateChallengeUseCase(repository).execute(CreateChallengeCommand(definition()))
    provider = FakeLLMProvider(
        LLMExecutionResult("YES", "fake"),
        LLMExecutionResult("NO", "fake"),
    )
    counter = FakePromptTokenCounter(8)
    result = await AdminTestUseCase(
        repository,
        provider,
        EvaluationEngine.with_builtin_graders(),
        counter,
        ScoringService(),
    ).execute("admin-test", "Return the correct label.")
    assert result.passed_count == 2
    assert result.total_count == 2
    assert result.accuracy == 100
    assert len(provider.requests) == 2
    assert result.visible_results[0].expected_output == "YES"
    assert result.hidden_results[0].expected_output == "NO"


@async_test
async def test_builder_authors_text_challenges_only() -> None:
    repository = MemoryAdminRepository()
    await CreateChallengeUseCase(repository).execute(CreateChallengeCommand(definition()))
    assert repository.record.version.challenge_type is ChallengeType.TEXT


@async_test
async def test_builder_refuses_to_publish_or_test_unsupported_challenge_types() -> None:
    repository = MemoryAdminRepository()
    await CreateChallengeUseCase(repository).execute(CreateChallengeCommand(definition()))
    repository.record = replace(
        repository.record,
        version=replace(
            repository.record.version,
            challenge_type=ChallengeType.IMAGE,
            application_config=None,
        ),
    )
    provider = FakeLLMProvider(LLMExecutionResult("YES", "fake"))

    with pytest.raises(AdminChallengeStateError, match="image"):
        await PublishChallengeUseCase(repository).execute("admin-test")
    with pytest.raises(AdminChallengeStateError, match="image"):
        await AdminTestUseCase(
            repository,
            provider,
            EvaluationEngine.with_builtin_graders(),
            FakePromptTokenCounter(8),
            ScoringService(),
        ).execute("admin-test", "Return the correct label.")
    assert repository.record.challenge.current_version_id is None
    assert provider.requests == []
