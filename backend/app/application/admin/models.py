from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.domains.application.models import ApplicationLimits, ApplicationViewport
from app.domains.challenges.models import (
    Challenge,
    ChallengeTrack,
    ChallengeType,
    ChallengeVersion,
    Difficulty,
    PublicationState,
)
from app.domains.evaluation.configuration import GraderType
from app.domains.evaluation.results import FailureReason
from app.domains.evaluation.test_cases import HiddenTestCase
from app.domains.evaluation.types import EvaluationValue
from app.domains.execution.models import ChallengeExecutionResult


@dataclass(frozen=True, slots=True)
class GraderAuthoringSpec:
    grader_type: GraderType
    allowed_labels: tuple[str, ...] = ()
    schema: dict[str, EvaluationValue] | None = None
    fields: tuple[str, ...] = ()
    order_matters: bool = True


@dataclass(frozen=True, slots=True)
class ExampleAuthoringSpec:
    input: EvaluationValue
    expected_output: EvaluationValue
    explanation: str | None = None


@dataclass(frozen=True, slots=True)
class TestCaseAuthoringSpec:
    id: str
    input: EvaluationValue
    expected_output: EvaluationValue
    grader: GraderAuthoringSpec


@dataclass(frozen=True, slots=True)
class EfficiencyTierAuthoringSpec:
    max_tokens: int
    score: float


@dataclass(frozen=True, slots=True)
class ScoringAuthoringSpec:
    accuracy_weight: float
    efficiency_weight: float
    efficiency_tiers: tuple[EfficiencyTierAuthoringSpec, ...]
    score_above_max: float
    one_star: float
    two_stars: float
    three_stars: float
    three_star_max_prompt_tokens: int | None


@dataclass(frozen=True, slots=True)
class ModelAuthoringSpec:
    model_id: str
    temperature: float
    max_output_tokens: int
    system_wrapper: str | None
    configuration_version: str | None = None
    reasoning_effort: str | None = None


@dataclass(frozen=True, slots=True)
class ApplicationAuthoringSpec:
    package_id: str
    editable_files: tuple[str, ...]
    visible_checks: tuple[str, ...]
    hidden_checks: tuple[str, ...]
    viewports: tuple[ApplicationViewport, ...]
    limits: ApplicationLimits


@dataclass(frozen=True, slots=True)
class ChallengeAuthoringSpec:
    slug: str
    track: ChallengeTrack
    order: int
    version: str
    title: str
    description: str
    objective: str
    constraints: tuple[str, ...]
    difficulty: Difficulty
    visible_examples: tuple[ExampleAuthoringSpec, ...]
    visible_test_cases: tuple[TestCaseAuthoringSpec, ...]
    hidden_test_cases: tuple[TestCaseAuthoringSpec, ...]
    prompt_token_limit: int | None
    default_grader: GraderAuthoringSpec
    scoring: ScoringAuthoringSpec
    model: ModelAuthoringSpec
    challenge_type: ChallengeType = ChallengeType.TEXT
    application: ApplicationAuthoringSpec | None = None


@dataclass(frozen=True, slots=True)
class CreateChallengeCommand:
    definition: ChallengeAuthoringSpec
    publish: bool = False


@dataclass(frozen=True, slots=True)
class UpdateChallengeDraftCommand:
    challenge_slug: str
    definition: ChallengeAuthoringSpec


@dataclass(frozen=True, slots=True)
class VersionMetadata:
    version: str
    publication_state: PublicationState
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AdminChallengeRecord:
    challenge: Challenge
    version: ChallengeVersion
    hidden_test_cases: tuple[HiddenTestCase, ...]
    versions: tuple[VersionMetadata, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AdminChallengeSummary:
    slug: str
    title: str
    track: ChallengeTrack
    difficulty: Difficulty
    order: int
    version: str
    current_version: str | None
    publication_state: PublicationState
    visible_test_count: int
    hidden_test_count: int
    created_at: datetime
    updated_at: datetime
    challenge_type: ChallengeType = ChallengeType.TEXT


@dataclass(frozen=True, slots=True)
class AdminMutationResult:
    challenge_id: str
    slug: str
    track: ChallengeTrack
    version: str
    publication_state: PublicationState
    message: str


@dataclass(frozen=True, slots=True)
class AdminTestCaseResult:
    id: str
    visibility: Literal["visible", "hidden"]
    input: EvaluationValue
    expected_output: EvaluationValue
    actual_output: EvaluationValue
    passed: bool
    failure_reason: FailureReason | None


@dataclass(frozen=True, slots=True)
class AdminChallengeTestResult:
    challenge_slug: str
    challenge_version_id: str
    prompt_tokens: int
    passed_count: int
    total_count: int
    accuracy: float
    efficiency: float
    final_score: float
    stars: int
    visible_results: tuple[AdminTestCaseResult, ...]
    hidden_results: tuple[AdminTestCaseResult, ...]
    application_execution: ChallengeExecutionResult | None = None
    visible_check_ids: tuple[str, ...] = ()
    hidden_check_ids: tuple[str, ...] = ()
