from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.api.schemas.challenges import (
    ApplicationAgentResponse,
    ApplicationBuildResponse,
    ApplicationCheckResponse,
    ApplicationRunResponse,
    ChangedFileResponse,
    ScreenshotResponse,
)
from app.application.admin.models import (
    AdminChallengeRecord,
    AdminChallengeSummary,
    AdminChallengeTestResult,
    AdminMutationResult,
    ApplicationAuthoringSpec,
    ChallengeAuthoringSpec,
    EfficiencyTierAuthoringSpec,
    ExampleAuthoringSpec,
    GraderAuthoringSpec,
    ModelAuthoringSpec,
    ScoringAuthoringSpec,
    TestCaseAuthoringSpec,
)
from app.domains.application.models import (
    ApplicationChallengeConfig,
    ApplicationLimits,
    ApplicationViewport,
)
from app.domains.application.packages import ApplicationPackage
from app.domains.challenges.models import ChallengeTrack, ChallengeType, Difficulty
from app.domains.evaluation.configuration import (
    AllowedLabelGraderConfig,
    ArrayComparisonGraderConfig,
    FieldComparisonGraderConfig,
    GraderConfiguration,
    GraderType,
    JsonSchemaGraderConfig,
)
from app.domains.evaluation.test_cases import HiddenTestCase, VisibleTestCase
from app.domains.execution.models import BuildArtifact, ChangedFilesArtifact, ScreenshotArtifact


class ExactMatchGraderInput(BaseModel):
    type: Literal["exact_match"] = "exact_match"


class CaseInsensitiveGraderInput(BaseModel):
    type: Literal["case_insensitive_exact_match"] = "case_insensitive_exact_match"


class AllowedLabelGraderInput(BaseModel):
    type: Literal["allowed_label"] = "allowed_label"
    allowed_labels: list[str] = Field(min_length=1)


class JsonSchemaGraderInput(BaseModel):
    type: Literal["json_schema"] = "json_schema"
    schema_: dict[str, JsonValue] = Field(alias="schema")
    model_config = ConfigDict(populate_by_name=True)


class FieldComparisonGraderInput(BaseModel):
    type: Literal["field_comparison"] = "field_comparison"
    fields: list[str] = Field(min_length=1)


class ArrayComparisonGraderInput(BaseModel):
    type: Literal["array_comparison"] = "array_comparison"
    order_matters: bool = True


GraderInput = Annotated[
    ExactMatchGraderInput
    | CaseInsensitiveGraderInput
    | AllowedLabelGraderInput
    | JsonSchemaGraderInput
    | FieldComparisonGraderInput
    | ArrayComparisonGraderInput,
    Field(discriminator="type"),
]


def _grader_spec(value: GraderInput) -> GraderAuthoringSpec:
    return GraderAuthoringSpec(
        grader_type=GraderType(value.type),
        allowed_labels=tuple(getattr(value, "allowed_labels", ())),
        schema=getattr(value, "schema_", None),
        fields=tuple(getattr(value, "fields", ())),
        order_matters=getattr(value, "order_matters", True),
    )


def _grader_response(config: GraderConfiguration) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {"type": config.grader_type.value}
    if isinstance(config, AllowedLabelGraderConfig):
        result["allowed_labels"] = sorted(config.allowed_labels)
    elif isinstance(config, JsonSchemaGraderConfig):
        result["schema"] = dict(config.schema)
    elif isinstance(config, FieldComparisonGraderConfig):
        result["fields"] = list(config.fields)
    elif isinstance(config, ArrayComparisonGraderConfig):
        result["order_matters"] = config.order_matters
    return result


class VisibleExampleInput(BaseModel):
    input: JsonValue
    expected_output: JsonValue
    explanation: str | None = None


class TestCaseInput(BaseModel):
    id: str = Field(min_length=1)
    input: JsonValue
    expected_output: JsonValue
    grader: GraderInput = Field(default_factory=ExactMatchGraderInput)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_grader_type(cls, value: object) -> object:
        if isinstance(value, dict) and "grader" not in value and "grader_type" in value:
            copied = dict(value)
            copied["grader"] = {"type": copied.pop("grader_type")}
            return copied
        return value


class EfficiencyTierInput(BaseModel):
    max_tokens: int = Field(ge=0)
    score: float = Field(ge=0, le=100)


class ScoringInput(BaseModel):
    accuracy_weight: float = 0.8
    efficiency_weight: float = 0.2
    efficiency_tiers: list[EfficiencyTierInput] = Field(
        default_factory=lambda: [
            EfficiencyTierInput(max_tokens=60, score=100),
            EfficiencyTierInput(max_tokens=100, score=90),
            EfficiencyTierInput(max_tokens=150, score=75),
            EfficiencyTierInput(max_tokens=250, score=60),
        ]
    )
    score_above_max: float = Field(default=40, ge=0, le=100)
    one_star: float = Field(default=70, ge=0, le=100)
    two_stars: float = Field(default=90, ge=0, le=100)
    three_stars: float = Field(default=100, ge=0, le=100)
    three_star_max_prompt_tokens: int | None = Field(default=60, ge=0)


class ModelInput(BaseModel):
    model_id: str = Field(default="openai/gpt-oss-20b", min_length=1)
    temperature: float = Field(default=0, ge=0, le=2)
    max_output_tokens: int = Field(default=16, ge=1)
    system_wrapper: str | None = (
        "Apply the player's instruction to the next user message, which contains the "
        "test input. Do not add facts that are not present in that input."
    )
    configuration_version: str | None = None
    reasoning_effort: Literal["low", "medium", "high"] | None = None


class ApplicationLimitsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    agent_timeout_seconds: float = Field(default=90, gt=0, le=180)
    build_timeout_seconds: float = Field(default=20, gt=0, le=180)
    browser_timeout_seconds: float = Field(default=20, gt=0, le=180)
    max_file_bytes: int = Field(default=32000, gt=0, le=64000)
    max_files: int = Field(default=2, gt=0, le=8)
    max_log_chars: int = Field(default=2000, gt=0, le=4000)


class ApplicationViewportInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    width: int = Field(ge=280, le=1920)
    height: int = Field(ge=320, le=1200)
    label: str = Field(min_length=1, max_length=60)
    screenshot: bool = False


class ApplicationAuthoringInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    package_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    editable_files: list[str] = Field(min_length=1, max_length=8)
    visible_checks: list[str] = Field(min_length=1, max_length=30)
    hidden_checks: list[str] = Field(min_length=1, max_length=30)
    viewports: list[ApplicationViewportInput] = Field(min_length=1, max_length=6)
    limits: ApplicationLimitsInput

    def to_spec(self) -> ApplicationAuthoringSpec:
        return ApplicationAuthoringSpec(
            self.package_id,
            tuple(self.editable_files),
            tuple(self.visible_checks),
            tuple(self.hidden_checks),
            tuple(ApplicationViewport(**v.model_dump()) for v in self.viewports),
            ApplicationLimits(**self.limits.model_dump()),
        )

    @classmethod
    def from_config(cls, config: ApplicationChallengeConfig) -> "ApplicationAuthoringInput":
        from dataclasses import asdict

        return cls(
            package_id=config.starter_project,
            editable_files=list(config.editable_files),
            visible_checks=list(config.visible_checks),
            hidden_checks=list(config.hidden_checks),
            viewports=[ApplicationViewportInput(**asdict(v)) for v in config.viewports],
            limits=ApplicationLimitsInput(**asdict(config.limits)),
        )


class PackageCheckResponse(BaseModel):
    id: str
    label: str
    implementation: str
    viewports: list[str]
    count: int
    min_width_ratio: float
    tolerance: float


class ApplicationPackageResponse(BaseModel):
    execution_mode: str = "static"
    runtime_metadata: dict[str, object] | None = None
    id: str
    display_name: str
    description: str
    defaults: ApplicationAuthoringInput
    visible_checks: list[PackageCheckResponse]
    hidden_checks: list[PackageCheckResponse]

    @classmethod
    def from_package(cls, package: ApplicationPackage) -> "ApplicationPackageResponse":
        def checks(ids):
            return [
                PackageCheckResponse(
                    id=c.id,
                    label=c.label,
                    implementation=c.implementation,
                    viewports=list(c.parameters.viewports),
                    count=c.parameters.count,
                    min_width_ratio=c.parameters.min_width_ratio,
                    tolerance=c.parameters.tolerance,
                )
                for c in package.selected_checks(ids)
            ]

        return cls(
            execution_mode=package.defaults.execution_mode.value,
            runtime_metadata=asdict(package.sandbox) if package.sandbox else None,
            id=package.id,
            display_name=package.display_name,
            description=package.description,
            defaults=ApplicationAuthoringInput.from_config(package.defaults),
            visible_checks=checks(package.defaults.visible_checks),
            hidden_checks=checks(package.defaults.hidden_checks),
        )


class UpsertChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_type: Literal["text", "application"] = "text"
    application: ApplicationAuthoringInput | None = None
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    track: Literal["control", "extract", "classify", "structure"]
    order: int = Field(ge=0)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard", "boss"]
    constraints: list[str] = Field(default_factory=list)
    visible_examples: list[VisibleExampleInput] = Field(default_factory=list)
    visible_test_cases: list[TestCaseInput] = Field(default_factory=list)
    hidden_test_cases: list[TestCaseInput] = Field(default_factory=list)
    prompt_token_limit: int | None = Field(default=300, ge=1)
    default_grader: GraderInput = Field(default_factory=ExactMatchGraderInput)
    model: ModelInput = Field(default_factory=ModelInput)
    scoring: ScoringInput = Field(default_factory=ScoringInput)
    version: str = Field(default="1", min_length=1)
    publication_state: str = Field(default="published", pattern="^(draft|published)$")

    @model_validator(mode="after")
    def validate_family(self):
        if (self.challenge_type == "application") != (self.application is not None):
            raise ValueError("Application configuration is required only for APPLICATION.")
        if self.challenge_type == "application" and (
            self.visible_test_cases or self.hidden_test_cases or self.visible_examples
        ):
            raise ValueError("APPLICATION uses package checks, not text cases.")
        return self

    def to_spec(self) -> ChallengeAuthoringSpec:
        return ChallengeAuthoringSpec(
            challenge_type=ChallengeType(self.challenge_type),
            application=self.application.to_spec() if self.application else None,
            slug=self.slug,
            track=ChallengeTrack(self.track),
            order=self.order,
            version=self.version,
            title=self.title,
            description=self.description,
            objective=self.objective,
            constraints=tuple(self.constraints),
            difficulty=Difficulty(self.difficulty),
            visible_examples=tuple(
                ExampleAuthoringSpec(item.input, item.expected_output, item.explanation)
                for item in self.visible_examples
            ),
            visible_test_cases=tuple(
                TestCaseAuthoringSpec(
                    item.id, item.input, item.expected_output, _grader_spec(item.grader)
                )
                for item in self.visible_test_cases
            ),
            hidden_test_cases=tuple(
                TestCaseAuthoringSpec(
                    item.id, item.input, item.expected_output, _grader_spec(item.grader)
                )
                for item in self.hidden_test_cases
            ),
            prompt_token_limit=self.prompt_token_limit,
            default_grader=_grader_spec(self.default_grader),
            scoring=ScoringAuthoringSpec(
                accuracy_weight=self.scoring.accuracy_weight,
                efficiency_weight=self.scoring.efficiency_weight,
                efficiency_tiers=tuple(
                    EfficiencyTierAuthoringSpec(item.max_tokens, item.score)
                    for item in self.scoring.efficiency_tiers
                ),
                score_above_max=self.scoring.score_above_max,
                one_star=self.scoring.one_star,
                two_stars=self.scoring.two_stars,
                three_stars=self.scoring.three_stars,
                three_star_max_prompt_tokens=self.scoring.three_star_max_prompt_tokens,
            ),
            model=ModelAuthoringSpec(
                model_id=self.model.model_id,
                temperature=self.model.temperature,
                max_output_tokens=self.model.max_output_tokens,
                system_wrapper=self.model.system_wrapper,
                configuration_version=self.model.configuration_version,
                reasoning_effort=self.model.reasoning_effort,
            ),
        )


class UpsertChallengeResponse(BaseModel):
    challenge_id: str
    slug: str
    track: str
    version: str
    publication_state: str
    message: str

    @classmethod
    def from_result(cls, result: AdminMutationResult) -> "UpsertChallengeResponse":
        return cls(
            challenge_id=result.challenge_id,
            slug=result.slug,
            track=result.track.value,
            version=result.version,
            publication_state=result.publication_state.value,
            message=result.message,
        )


class AdminChallengeListItemResponse(BaseModel):
    challenge_type: str
    slug: str
    title: str
    track: str
    difficulty: str
    order: int
    version: str
    current_version: str | None
    publication_state: str
    visible_test_count: int
    hidden_test_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_summary(cls, item: AdminChallengeSummary) -> "AdminChallengeListItemResponse":
        return cls(
            challenge_type=item.challenge_type.value,
            slug=item.slug,
            title=item.title,
            track=item.track.value,
            difficulty=item.difficulty.value,
            order=item.order,
            version=item.version,
            current_version=item.current_version,
            publication_state=item.publication_state.value,
            visible_test_count=item.visible_test_count,
            hidden_test_count=item.hidden_test_count,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class AdminChallengeListResponse(BaseModel):
    challenges: list[AdminChallengeListItemResponse]


class AdminVersionResponse(BaseModel):
    version: str
    publication_state: str
    created_at: datetime


class AdminChallengeDetailResponse(BaseModel):
    challenge_type: Literal["text", "application"]
    application: ApplicationAuthoringInput | None
    id: str
    slug: str
    track: str
    order: int
    current_version: str | None
    version: str
    title: str
    description: str
    objective: str
    constraints: list[str]
    difficulty: str
    visible_examples: list[VisibleExampleInput]
    visible_test_cases: list[TestCaseInput]
    hidden_test_cases: list[TestCaseInput]
    prompt_token_limit: int | None
    default_grader: dict[str, JsonValue]
    model: ModelInput
    scoring: ScoringInput
    publication_state: str
    versions: list[AdminVersionResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: AdminChallengeRecord) -> "AdminChallengeDetailResponse":
        version = record.version

        def test_case(item: VisibleTestCase | HiddenTestCase) -> TestCaseInput:
            return TestCaseInput.model_validate(
                {
                    "id": item.id,
                    "input": item.input,
                    "expected_output": item.expected_output,
                    "grader": _grader_response(item.grader_config),
                }
            )

        scoring = version.scoring_config
        return cls(
            challenge_type=version.challenge_type.value,
            application=ApplicationAuthoringInput.from_config(version.application_config)
            if version.application_config
            else None,
            id=record.challenge.id,
            slug=record.challenge.slug,
            track=record.challenge.track.value,
            order=record.challenge.order,
            current_version=record.challenge.current_version_id,
            version=version.version_id,
            title=version.title,
            description=version.description,
            objective=version.objective,
            constraints=list(version.constraints),
            difficulty=version.difficulty.value,
            visible_examples=[
                VisibleExampleInput(
                    input=item.input,
                    expected_output=item.expected_output,
                    explanation=item.explanation,
                )
                for item in version.visible_examples
            ],
            visible_test_cases=[test_case(item) for item in version.visible_test_cases],
            hidden_test_cases=[test_case(item) for item in record.hidden_test_cases],
            prompt_token_limit=version.prompt_token_limit,
            default_grader=_grader_response(version.evaluation_config.default_grader),
            model=ModelInput(
                model_id=version.model_config.model_id,
                temperature=version.model_config.temperature,
                max_output_tokens=version.model_config.max_output_tokens,
                system_wrapper=version.model_config.system_wrapper,
                configuration_version=version.model_config.configuration_version,
                reasoning_effort=version.model_config.reasoning_effort.value
                if version.model_config.reasoning_effort
                else None,
            ),
            scoring=ScoringInput(
                accuracy_weight=scoring.accuracy_weight,
                efficiency_weight=scoring.efficiency_weight,
                efficiency_tiers=[
                    EfficiencyTierInput(max_tokens=item.max_tokens, score=item.score)
                    for item in scoring.efficiency_thresholds.tiers
                ],
                score_above_max=scoring.efficiency_thresholds.score_above_max,
                one_star=scoring.star_thresholds.one_star,
                two_stars=scoring.star_thresholds.two_stars,
                three_stars=scoring.star_thresholds.three_stars,
                three_star_max_prompt_tokens=scoring.star_thresholds.three_star_max_prompt_tokens,
            ),
            publication_state=version.publication_state.value,
            versions=[
                AdminVersionResponse(
                    version=item.version,
                    publication_state=item.publication_state.value,
                    created_at=item.created_at,
                )
                for item in record.versions
            ],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class PublishChallengeRequest(BaseModel):
    version: str | None = None


class TestChallengeRequest(BaseModel):
    prompt: str = Field(min_length=1)


class AdminTestCaseResponse(BaseModel):
    id: str
    input: JsonValue
    expected: JsonValue
    actual: JsonValue
    passed: bool
    failure_reason: str | None


class TestChallengeResponse(BaseModel):
    challenge_type: Literal["text", "application"] = "text"
    application: ApplicationRunResponse | None = None
    hidden_checks: list[ApplicationCheckResponse] = Field(default_factory=list)
    challenge: str
    version: str
    prompt_tokens: int
    passed: int
    total: int
    accuracy: float
    efficiency: float
    score: float
    stars: int
    visible_tests: list[AdminTestCaseResponse]
    hidden_tests: list[AdminTestCaseResponse]

    @classmethod
    def from_result(cls, result: AdminChallengeTestResult) -> "TestChallengeResponse":
        def convert(item) -> AdminTestCaseResponse:
            return AdminTestCaseResponse(
                id=item.id,
                input=item.input,
                expected=item.expected_output,
                actual=item.actual_output,
                passed=item.passed,
                failure_reason=(item.failure_reason.value if item.failure_reason else None),
            )

        return cls(
            challenge_type="application" if result.application_execution else "text",
            application=_admin_application_result(result),
            hidden_checks=_admin_checks(result, result.hidden_check_ids),
            challenge=result.challenge_slug,
            version=result.challenge_version_id,
            prompt_tokens=result.prompt_tokens,
            passed=result.passed_count,
            total=result.total_count,
            accuracy=round(result.accuracy, 2),
            efficiency=round(result.efficiency, 2),
            score=result.final_score,
            stars=result.stars,
            visible_tests=[convert(item) for item in result.visible_results],
            hidden_tests=[convert(item) for item in result.hidden_results],
        )


def _admin_checks(
    result: AdminChallengeTestResult, ids: tuple[str, ...]
) -> list[ApplicationCheckResponse]:
    execution = result.application_execution
    if execution is None:
        return []
    return [
        ApplicationCheckResponse(
            id=c.test_case_id,
            label=c.label or "Check",
            passed=c.grade.passed,
            message=c.grade.diagnostic.message if c.grade.diagnostic else None,
        )
        for c in execution.check_results
        if c.test_case_id in ids
    ]


def _admin_application_result(result: AdminChallengeTestResult) -> ApplicationRunResponse | None:
    execution = result.application_execution
    if execution is None:
        return None
    changes = next(a for a in execution.artifacts if isinstance(a, ChangedFilesArtifact))
    build = next(a for a in execution.artifacts if isinstance(a, BuildArtifact))
    visible = _admin_checks(result, result.visible_check_ids)
    return ApplicationRunResponse(
        challenge=result.challenge_slug,
        challenge_id=result.challenge_slug,
        version=result.challenge_version_id,
        passed=sum(c.passed for c in visible),
        total=len(visible),
        evaluation_score=round(sum(c.passed for c in visible) / len(visible) * 100, 2),
        agent=ApplicationAgentResponse(status=changes.agent_status.value, message=changes.message),
        changed_files=[
            ChangedFileResponse(path=f.path, additions=f.additions, deletions=f.deletions)
            for f in changes.files
        ],
        build=ApplicationBuildResponse(status=build.status.value, log=build.log),
        checks=visible,
        screenshots=[
            ScreenshotResponse.from_artifact(a)
            for a in execution.artifacts
            if isinstance(a, ScreenshotArtifact)
        ],
    )
