from dataclasses import dataclass

from app.application.challenges.errors import RunChallengeRequestError
from app.domains.evaluation.results import FailureReason
from app.domains.evaluation.types import EvaluationValue


@dataclass(frozen=True, slots=True)
class RunChallengeCommand:
    challenge_slug: str
    player_prompt: str

    def __post_init__(self) -> None:
        slug = self.challenge_slug.strip()
        if not slug:
            raise RunChallengeRequestError("Challenge slug cannot be blank.")
        if not self.player_prompt.strip():
            raise RunChallengeRequestError("Player prompt cannot be blank.")
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
