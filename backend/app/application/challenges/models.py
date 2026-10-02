from dataclasses import dataclass

from app.application.challenges.errors import (
    RunChallengeRequestError,
    SubmitChallengeRequestError,
)
from app.domains.evaluation.results import FailureReason
from app.domains.evaluation.types import EvaluationValue
from app.domains.execution.models import (
    AgentStatus,
    BuildArtifact,
    ChangedFilesArtifact,
    ScreenshotArtifact,
)


@dataclass(frozen=True, slots=True)
class RunChallengeCommand:
    challenge_slug: str
    player_prompt: str
    owner_user_id: str | None = None

    def __post_init__(self) -> None:
        slug = self.challenge_slug.strip()
        if not slug:
            raise RunChallengeRequestError("Challenge slug cannot be blank.")
        if not self.player_prompt.strip():
            raise RunChallengeRequestError("Player prompt cannot be blank.")
        if self.owner_user_id is not None and not self.owner_user_id.strip():
            raise RunChallengeRequestError("Owner ID cannot be blank when provided.")
        object.__setattr__(self, "challenge_slug", slug)


@dataclass(frozen=True, slots=True)
class VisibleTestRunResult:
    test_id: str
    input: EvaluationValue
    expected_output: EvaluationValue
    actual_output: EvaluationValue
    passed: bool
    failure_reason: FailureReason | None


@dataclass(frozen=True, slots=True)
class RunChallengeResult:
    challenge_id: str
    challenge_slug: str
    challenge_version_id: str
    test_results: tuple[VisibleTestRunResult, ...]
    passed_count: int
    total_count: int
    accuracy: float


@dataclass(frozen=True, slots=True)
class SubmitChallengeCommand:
    challenge_slug: str
    player_prompt: str
    owner_user_id: str
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        slug = self.challenge_slug.strip()
        if not slug:
            raise SubmitChallengeRequestError("Challenge slug cannot be blank.")
        if not self.player_prompt.strip():
            raise SubmitChallengeRequestError("Player prompt cannot be blank.")
        owner_user_id = self.owner_user_id.strip()
        if not owner_user_id:
            raise SubmitChallengeRequestError("Authenticated owner ID cannot be blank.")
        object.__setattr__(self, "challenge_slug", slug)
        object.__setattr__(self, "owner_user_id", owner_user_id)
        if self.idempotency_key is not None:
            object.__setattr__(self, "idempotency_key", self.idempotency_key.strip())


@dataclass(frozen=True, slots=True)
class SubmitChallengeResult:
    """Aggregate-only hidden evaluation result safe for transport mapping."""

    challenge_slug: str
    challenge_version_id: str
    passed_count: int
    total_count: int
    accuracy: float
    prompt_tokens: int
    efficiency: float
    final_score: float
    stars: int
    xp_earned: int
    total_xp: int
    best_score: float
    best_stars: int
    completed: bool


@dataclass(frozen=True, slots=True)
class ApplicationCheckRunResult:
    check_id: str
    label: str
    passed: bool
    message: str | None


@dataclass(frozen=True, slots=True)
class ApplicationRunResult:
    """Visible APPLICATION Run feedback: what the agent built and the visible checks."""

    challenge_id: str
    challenge_slug: str
    challenge_version_id: str
    passed_count: int
    total_count: int
    evaluation_score: float
    checks: tuple[ApplicationCheckRunResult, ...]
    changes: ChangedFilesArtifact
    build: BuildArtifact
    screenshots: tuple[ScreenshotArtifact, ...]


@dataclass(frozen=True, slots=True)
class ApplicationSubmitResult:
    """Aggregate-only hidden APPLICATION evaluation; no per-check field exists."""

    challenge_slug: str
    challenge_version_id: str
    passed_count: int
    total_count: int
    evaluation_score: float
    prompt_tokens: int
    efficiency: float
    final_score: float
    stars: int
    xp_earned: int
    total_xp: int
    best_score: float
    best_stars: int
    completed: bool
    agent_status: AgentStatus
    screenshot: ScreenshotArtifact | None
