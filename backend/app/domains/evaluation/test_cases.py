from dataclasses import dataclass

from app.domains.evaluation.configuration import GraderConfiguration
from app.domains.evaluation.errors import EvaluationConfigurationError
from app.domains.evaluation.types import EvaluationValue


def _normalize_identifier(identifier: str, *, label: str) -> str:
    normalized = identifier.strip()
    if not normalized:
        raise EvaluationConfigurationError(f"{label} cannot be blank.")
    return normalized


@dataclass(frozen=True, slots=True)
class VisibleTestCase:
    """Executable test data that may be returned as Run feedback."""

    id: str
    input: EvaluationValue
    expected_output: EvaluationValue
    grader_config: GraderConfiguration

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _normalize_identifier(self.id, label="Test-case ID"))


@dataclass(frozen=True, slots=True)
class HiddenTestCase:
    """Server-only executable test data. Never use this type in an API response model."""

    id: str
    input: EvaluationValue
    expected_output: EvaluationValue
    grader_config: GraderConfiguration

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _normalize_identifier(self.id, label="Test-case ID"))


@dataclass(frozen=True, slots=True)
class HiddenTestSuite:
    """Server-only cases linked to the exact playable challenge version."""

    challenge_version_id: str
    test_cases: tuple[HiddenTestCase, ...]

    def __post_init__(self) -> None:
        version_id = _normalize_identifier(
            self.challenge_version_id,
            label="Challenge version ID",
        )
        test_cases = tuple(self.test_cases)
        if not test_cases:
            raise EvaluationConfigurationError("A hidden test suite cannot be empty.")
        test_ids = tuple(test_case.id for test_case in test_cases)
        if len(set(test_ids)) != len(test_ids):
            raise EvaluationConfigurationError("Hidden test-case IDs must be unique.")
        object.__setattr__(self, "challenge_version_id", version_id)
        object.__setattr__(self, "test_cases", test_cases)
