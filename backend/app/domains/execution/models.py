from dataclasses import dataclass
from enum import StrEnum

from app.domains.challenges.models import PlayableChallenge
from app.domains.evaluation.results import TestEvaluationResult
from app.domains.execution.errors import ChallengeExecutionError


@dataclass(frozen=True, slots=True)
class ChallengeExecutionRequest:
    """Family-neutral input: the exact playable version plus the player-authored prompt."""

    playable: PlayableChallenge
    player_prompt: str

    def __post_init__(self) -> None:
        if not self.player_prompt.strip():
            raise ChallengeExecutionError("Player prompt cannot be blank.")


@dataclass(frozen=True, slots=True)
class TextOutputArtifact:
    """Model text generated for one executed text test case."""

    test_case_id: str
    output_text: str


@dataclass(frozen=True, slots=True)
class ScreenshotArtifact:
    """PNG of the rendered result at one fixed viewport."""

    viewport: str
    width: int
    height: int
    png: bytes
    label: str = ""


class BuildStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class BuildArtifact:
    """Outcome of the predefined build. `log` is sanitized and truncated before storage."""

    status: BuildStatus
    log: str


class AgentStatus(StrEnum):
    APPLIED = "applied"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ChangedFile:
    path: str
    additions: int
    deletions: int


@dataclass(frozen=True, slots=True)
class ChangedFilesArtifact:
    """What the coding agent changed: a line-count summary, never the full source tree."""

    agent_status: AgentStatus
    message: str | None
    files: tuple[ChangedFile, ...]


# Each family adds its own typed variants; IMAGE would add a generated-image artifact.
type ExecutionArtifact = (
    TextOutputArtifact | ScreenshotArtifact | BuildArtifact | ChangedFilesArtifact
)


@dataclass(frozen=True, slots=True)
class ChallengeExecutionResult:
    """Internal normalized outcome of one execution.

    `evaluation_score` (0-100) is the normalized scoring input. For TEXT it is exactly the
    deterministic pass-rate accuracy; other families may define it differently. The result
    may describe hidden checks, so it is never serialized directly: Run and Submit each map
    it to their own purpose-specific result.
    """

    evaluation_score: float
    passed_checks: int
    total_checks: int
    check_results: tuple[TestEvaluationResult, ...]
    artifacts: tuple[ExecutionArtifact, ...]

    def __post_init__(self) -> None:
        if self.total_checks <= 0:
            raise ChallengeExecutionError("An execution result requires at least one check.")
        if not 0 <= self.passed_checks <= self.total_checks:
            raise ChallengeExecutionError("Passed checks must be between zero and total checks.")
        if not 0.0 <= self.evaluation_score <= 100.0:
            raise ChallengeExecutionError("Evaluation score must be between 0 and 100.")
        object.__setattr__(self, "check_results", tuple(self.check_results))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
