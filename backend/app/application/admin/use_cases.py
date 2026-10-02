from dataclasses import replace
from datetime import UTC, datetime

from app.application.admin.errors import (
    AdminChallengeConflictError,
    AdminChallengeNotFoundError,
    AdminChallengeStateError,
)
from app.application.admin.models import (
    AdminChallengeRecord,
    AdminChallengeTestResult,
    AdminMutationResult,
    AdminTestCaseResult,
    ChallengeAuthoringSpec,
    CreateChallengeCommand,
    GraderAuthoringSpec,
    UpdateChallengeDraftCommand,
    VersionMetadata,
)
from app.application.admin.ports import AdminChallengeRepository
from app.application.challenges.errors import PromptTooLongError
from app.domains.application.models import ApplicationChallengeConfig
from app.domains.application.ports import ApplicationPackageLoader
from app.domains.challenges.models import (
    Challenge,
    ChallengeType,
    ChallengeVersion,
    PlayableChallenge,
    PublicationState,
    VisibleExample,
)
from app.domains.evaluation.configuration import (
    AllowedLabelGraderConfig,
    ArrayComparisonGraderConfig,
    CaseInsensitiveExactMatchGraderConfig,
    EvaluationConfiguration,
    ExactMatchGraderConfig,
    FieldComparisonGraderConfig,
    GraderConfiguration,
    GraderType,
    JsonSchemaGraderConfig,
    ModelConfiguration,
    ReasoningEffort,
)
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionRequest
from app.domains.evaluation.ports import LLMProvider
from app.domains.evaluation.test_cases import HiddenTestCase, VisibleTestCase
from app.domains.execution.application import ApplicationChallengeExecutor
from app.domains.execution.models import ChallengeExecutionRequest
from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    EfficiencyTier,
    ScoringConfiguration,
    StarThresholds,
)
from app.domains.scoring.ports import PromptTokenCounter
from app.domains.scoring.service import ScoringService


def _grader(spec: GraderAuthoringSpec) -> GraderConfiguration:
    if spec.grader_type is GraderType.EXACT_MATCH:
        return ExactMatchGraderConfig()
    if spec.grader_type is GraderType.CASE_INSENSITIVE_EXACT_MATCH:
        return CaseInsensitiveExactMatchGraderConfig()
    if spec.grader_type is GraderType.ALLOWED_LABEL:
        return AllowedLabelGraderConfig(frozenset(spec.allowed_labels))
    if spec.grader_type is GraderType.JSON_SCHEMA:
        return JsonSchemaGraderConfig(spec.schema or {})
    if spec.grader_type is GraderType.FIELD_COMPARISON:
        return FieldComparisonGraderConfig(spec.fields)
    return ArrayComparisonGraderConfig(order_matters=spec.order_matters)


def build_record(
    spec: ChallengeAuthoringSpec,
    *,
    challenge_id: str,
    current_version: str | None,
    publication_state: PublicationState,
    versions: tuple[VersionMetadata, ...] = (),
    created_at: datetime | None = None,
    application_config: ApplicationChallengeConfig | None = None,
) -> AdminChallengeRecord:
    now = datetime.now(UTC)
    scoring = ScoringConfiguration(
        accuracy_weight=spec.scoring.accuracy_weight,
        efficiency_weight=spec.scoring.efficiency_weight,
        efficiency_thresholds=EfficiencyThresholds(
            tiers=tuple(
                EfficiencyTier(tier.max_tokens, tier.score)
                for tier in spec.scoring.efficiency_tiers
            ),
            score_above_max=spec.scoring.score_above_max,
        ),
        star_thresholds=StarThresholds(
            one_star=spec.scoring.one_star,
            two_stars=spec.scoring.two_stars,
            three_stars=spec.scoring.three_stars,
            three_star_max_prompt_tokens=spec.scoring.three_star_max_prompt_tokens,
        ),
    )
    model = ModelConfiguration(
        model_id=spec.model.model_id,
        temperature=spec.model.temperature,
        max_output_tokens=spec.model.max_output_tokens,
        configuration_version=(
            spec.model.configuration_version or f"{spec.slug}-model-v{spec.version}"
        ),
        system_wrapper=spec.model.system_wrapper,
        reasoning_effort=ReasoningEffort(spec.model.reasoning_effort)
        if spec.model.reasoning_effort
        else None,
    )
    visible = tuple(
        VisibleTestCase(item.id, item.input, item.expected_output, _grader(item.grader))
        for item in spec.visible_test_cases
    )
    hidden = tuple(
        HiddenTestCase(item.id, item.input, item.expected_output, _grader(item.grader))
        for item in spec.hidden_test_cases
    )
    version = ChallengeVersion(
        version_id=spec.version,
        challenge_id=challenge_id,
        title=spec.title,
        description=spec.description,
        objective=spec.objective,
        constraints=spec.constraints,
        difficulty=spec.difficulty,
        visible_examples=tuple(
            VisibleExample(item.input, item.expected_output, item.explanation)
            for item in spec.visible_examples
        ),
        visible_test_cases=visible,
        prompt_token_limit=spec.prompt_token_limit,
        evaluation_config=EvaluationConfiguration(default_grader=_grader(spec.default_grader)),
        scoring_config=scoring,
        model_config=model,
        publication_state=publication_state,
        challenge_type=spec.challenge_type,
        application_config=application_config,
    )
    return AdminChallengeRecord(
        challenge=Challenge(
            id=challenge_id,
            slug=spec.slug,
            track=spec.track,
            order=spec.order,
            current_version_id=current_version,
        ),
        version=version,
        hidden_test_cases=hidden,
        versions=versions,
        created_at=created_at or now,
        updated_at=now,
    )


class ListAdminChallengesUseCase:
    def __init__(self, repository: AdminChallengeRepository) -> None:
        self._repository = repository

    async def execute(self):
        return await self._repository.list_all()


class GetAdminChallengeUseCase:
    def __init__(self, repository: AdminChallengeRepository) -> None:
        self._repository = repository

    async def execute(self, slug: str) -> AdminChallengeRecord:
        record = await self._repository.get_by_slug(slug)
        if record is None:
            raise AdminChallengeNotFoundError(f"Challenge '{slug}' was not found.")
        return record


class CreateChallengeUseCase:
    def __init__(
        self, repository: AdminChallengeRepository, packages: ApplicationPackageLoader | None = None
    ) -> None:
        self._repository = repository
        self._packages = packages

    async def execute(self, command: CreateChallengeCommand) -> AdminMutationResult:
        if await self._repository.get_by_slug(command.definition.slug) is not None:
            raise AdminChallengeConflictError("A challenge with this slug already exists.")
        challenge_id = f"{command.definition.track.value}-{command.definition.slug}"
        record = build_record(
            command.definition,
            challenge_id=challenge_id,
            current_version=None,
            publication_state=PublicationState.DRAFT,
            application_config=_application_config(command.definition, self._packages),
        )
        if command.publish:
            _validate_publication(record, self._packages)
        await self._repository.create(record)
        if command.publish:
            record = await self._repository.publish(
                record.challenge.slug,
                record.version.version_id,
            )
        return _mutation(record, "Challenge created successfully.")


class UpdateChallengeDraftUseCase:
    def __init__(
        self, repository: AdminChallengeRepository, packages: ApplicationPackageLoader | None = None
    ) -> None:
        self._repository = repository
        self._packages = packages

    async def execute(self, command: UpdateChallengeDraftCommand) -> AdminMutationResult:
        existing = await self._repository.get_by_slug(command.challenge_slug)
        if existing is None:
            raise AdminChallengeNotFoundError(
                f"Challenge '{command.challenge_slug}' was not found."
            )
        _require_supported_challenge(existing)
        if existing.version.challenge_type is not command.definition.challenge_type:
            raise AdminChallengeStateError("Challenge type cannot change after creation.")
        if existing.version.version_id != command.definition.version:
            raise AdminChallengeConflictError("The requested draft version is not editable.")
        if existing.version.publication_state is not PublicationState.DRAFT:
            raise AdminChallengeStateError(
                "Published versions are immutable. Create a new draft version first."
            )
        if command.definition.slug != command.challenge_slug:
            raise AdminChallengeConflictError("A challenge slug cannot be changed after creation.")
        record = build_record(
            command.definition,
            challenge_id=existing.challenge.id,
            current_version=existing.challenge.current_version_id,
            publication_state=PublicationState.DRAFT,
            application_config=_application_config(command.definition, self._packages),
            versions=existing.versions,
            created_at=existing.created_at,
        )
        await self._repository.update_draft(record)
        return _mutation(record, "Draft saved successfully.")


class CreateChallengeVersionUseCase:
    def __init__(self, repository: AdminChallengeRepository) -> None:
        self._repository = repository

    async def execute(self, slug: str) -> AdminMutationResult:
        existing = await self._repository.get_by_slug(slug)
        if existing is None:
            raise AdminChallengeNotFoundError(f"Challenge '{slug}' was not found.")
        _require_supported_challenge(existing)
        if any(item.publication_state is PublicationState.DRAFT for item in existing.versions):
            raise AdminChallengeConflictError("This challenge already has an editable draft.")
        numeric = [int(item.version) for item in existing.versions if item.version.isdigit()]
        next_version = str(max(numeric, default=0) + 1)
        draft_version = replace(
            existing.version,
            version_id=next_version,
            publication_state=PublicationState.DRAFT,
            model_config=replace(
                existing.version.model_config,
                configuration_version=f"{slug}-model-v{next_version}",
            ),
        )
        now = datetime.now(UTC)
        record = replace(
            existing,
            version=draft_version,
            versions=existing.versions
            + (VersionMetadata(next_version, PublicationState.DRAFT, now),),
            updated_at=now,
        )
        await self._repository.create_version(record)
        return _mutation(record, "New draft version created.")


class PublishChallengeUseCase:
    def __init__(
        self, repository: AdminChallengeRepository, packages: ApplicationPackageLoader | None = None
    ) -> None:
        self._repository = repository
        self._packages = packages

    async def execute(self, slug: str, version: str | None = None) -> AdminMutationResult:
        record = await self._repository.get_by_slug(slug)
        if record is None:
            raise AdminChallengeNotFoundError(f"Challenge '{slug}' was not found.")
        target = version or record.version.version_id
        if record.version.version_id != target:
            raise AdminChallengeConflictError(
                "Only the current authoring version can be published."
            )
        if record.version.publication_state is not PublicationState.DRAFT:
            raise AdminChallengeStateError("Only a draft version can be published.")
        _validate_publication(record, self._packages)
        published = await self._repository.publish(slug, target)
        return _mutation(published, "Challenge published successfully.")


class UnpublishChallengeUseCase:
    def __init__(self, repository: AdminChallengeRepository) -> None:
        self._repository = repository

    async def execute(self, slug: str) -> AdminMutationResult:
        record = await self._repository.get_by_slug(slug)
        if record is None:
            raise AdminChallengeNotFoundError(f"Challenge '{slug}' was not found.")
        if record.challenge.current_version_id is None:
            raise AdminChallengeStateError("Challenge is not currently published.")
        unpublished = await self._repository.unpublish(slug)
        return _mutation(unpublished, "Challenge unpublished successfully.")


class TestChallengeUseCase:
    def __init__(
        self,
        repository: AdminChallengeRepository,
        llm_provider: LLMProvider,
        evaluation_engine: EvaluationEngine,
        prompt_token_counter: PromptTokenCounter,
        scoring_service: ScoringService,
        application_executor: ApplicationChallengeExecutor | None = None,
    ) -> None:
        self._repository = repository
        self._llm_provider = llm_provider
        self._evaluation_engine = evaluation_engine
        self._prompt_token_counter = prompt_token_counter
        self._scoring_service = scoring_service
        self._application_executor = application_executor

    async def execute(self, slug: str, player_prompt: str) -> AdminChallengeTestResult:
        record = await self._repository.get_by_slug(slug)
        if record is None:
            raise AdminChallengeNotFoundError(f"Challenge '{slug}' was not found.")
        if not player_prompt.strip():
            raise AdminChallengeStateError("Candidate prompt cannot be blank.")
        _require_supported_challenge(record)
        version = record.version
        prompt_tokens = self._prompt_token_counter.count(
            player_prompt, version.model_config.model_id
        )
        if version.prompt_token_limit is not None and prompt_tokens > version.prompt_token_limit:
            raise PromptTooLongError(
                actual_tokens=prompt_tokens,
                maximum_tokens=version.prompt_token_limit,
            )
        if version.challenge_type is ChallengeType.APPLICATION:
            if self._application_executor is None:
                raise AdminChallengeStateError("Application testing is unavailable.")
            # Drafts use the same executor via an in-memory playable view; nothing is published.
            playable = PlayableChallenge(
                replace(record.challenge, current_version_id=version.version_id),
                replace(version, publication_state=PublicationState.PUBLISHED),
            )
            execution = await self._application_executor.execute_admin(
                ChallengeExecutionRequest(playable, player_prompt)
            )
            scoring = self._scoring_service.calculate(
                prompt_tokens=prompt_tokens,
                accuracy=execution.evaluation_score,
                configuration=version.scoring_config,
            )
            config = version.application_config
            assert config is not None
            return AdminChallengeTestResult(
                slug,
                version.version_id,
                prompt_tokens,
                execution.passed_checks,
                execution.total_checks,
                execution.evaluation_score,
                scoring.efficiency,
                scoring.final_score,
                scoring.stars,
                (),
                (),
                execution,
                config.visible_checks,
                config.hidden_checks,
            )
        cases = tuple(version.visible_test_cases) + tuple(record.hidden_test_cases)
        if not cases:
            raise AdminChallengeStateError("Add at least one test before testing this challenge.")
        results: list[AdminTestCaseResult] = []
        for index, test_case in enumerate(cases):
            execution = await self._llm_provider.generate(
                LLMExecutionRequest(player_prompt, test_case.input, version.model_config)
            )
            grade = self._evaluation_engine.evaluate_test(test_case, execution.output_text).grade
            visibility = "visible" if index < len(version.visible_test_cases) else "hidden"
            results.append(
                AdminTestCaseResult(
                    id=test_case.id,
                    visibility=visibility,
                    input=test_case.input,
                    expected_output=test_case.expected_output,
                    actual_output=execution.output_text,
                    passed=grade.passed,
                    failure_reason=grade.failure_reason,
                )
            )
        passed = sum(result.passed for result in results)
        accuracy = passed / len(results) * 100
        scoring = self._scoring_service.calculate(
            prompt_tokens=prompt_tokens,
            accuracy=accuracy,
            configuration=version.scoring_config,
        )
        visible_results = tuple(item for item in results if item.visibility == "visible")
        hidden_results = tuple(item for item in results if item.visibility == "hidden")
        return AdminChallengeTestResult(
            challenge_slug=slug,
            challenge_version_id=version.version_id,
            prompt_tokens=prompt_tokens,
            passed_count=passed,
            total_count=len(results),
            accuracy=accuracy,
            efficiency=scoring.efficiency,
            final_score=scoring.final_score,
            stars=scoring.stars,
            visible_results=visible_results,
            hidden_results=hidden_results,
        )


def _require_supported_challenge(record: AdminChallengeRecord) -> None:
    if record.version.challenge_type not in {ChallengeType.TEXT, ChallengeType.APPLICATION}:
        raise AdminChallengeStateError(
            f"Challenge type '{record.version.challenge_type}' is not supported by the builder."
        )


def _mutation(record: AdminChallengeRecord, message: str) -> AdminMutationResult:
    return AdminMutationResult(
        challenge_id=record.challenge.id,
        slug=record.challenge.slug,
        track=record.challenge.track,
        version=record.version.version_id,
        publication_state=record.version.publication_state,
        message=message,
    )


def _application_config(
    spec: ChallengeAuthoringSpec, packages: ApplicationPackageLoader | None
) -> ApplicationChallengeConfig | None:
    if spec.challenge_type is ChallengeType.IMAGE:
        raise AdminChallengeStateError("IMAGE authoring is not supported.")
    if spec.challenge_type is ChallengeType.TEXT:
        if spec.application is not None:
            raise AdminChallengeStateError("TEXT cannot contain application configuration.")
        return None
    if packages is None or spec.application is None:
        raise AdminChallengeStateError("Select a registered application package.")
    if spec.visible_test_cases or spec.hidden_test_cases or spec.visible_examples:
        raise AdminChallengeStateError("APPLICATION uses package checks, not text test cases.")
    package = packages.load(spec.application.package_id)
    config = replace(
        package.defaults,
        editable_files=spec.application.editable_files,
        visible_checks=spec.application.visible_checks,
        hidden_checks=spec.application.hidden_checks,
        viewports=spec.application.viewports,
        limits=spec.application.limits,
    )
    packages.validate(config)
    return config


def _validate_publication(
    record: AdminChallengeRecord, packages: ApplicationPackageLoader | None
) -> None:
    _require_supported_challenge(record)
    if record.version.challenge_type is ChallengeType.APPLICATION:
        config = record.version.application_config
        if config is None or packages is None:
            raise AdminChallengeStateError("Application package validation is unavailable.")
        packages.validate(config)
    elif not record.version.visible_test_cases or not record.hidden_test_cases:
        raise AdminChallengeStateError(
            "Publishing requires at least one visible and one hidden test case."
        )


class ListApplicationPackagesUseCase:
    def __init__(self, packages: ApplicationPackageLoader) -> None:
        self._packages = packages

    def execute(self):
        return self._packages.catalog()
