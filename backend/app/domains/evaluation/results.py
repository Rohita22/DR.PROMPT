from dataclasses import dataclass
from enum import StrEnum

from app.domains.evaluation.errors import EvaluationConfigurationError


class FailureReason(StrEnum):
    OUTPUT_MISMATCH = "output_mismatch"
    INVALID_OUTPUT = "invalid_output"
    INVALID_LABEL = "invalid_label"
    INVALID_JSON = "invalid_json"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    FIELD_MISMATCH = "field_mismatch"
    EXPECTED_ARRAY = "expected_array"
    ARRAY_MISMATCH = "array_mismatch"
    MISSING_OUTPUT = "missing_output"


@dataclass(frozen=True, slots=True)
class SafeDiagnostic:
    """Small user-safe diagnostic; expected answers do not belong here."""

    code: str
    message: str | None = None

    def __post_init__(self) -> None:
        code = self.code.strip()
        if not code:
            raise EvaluationConfigurationError("Diagnostic code cannot be blank.")
        if self.message is not None and not self.message.strip():
            raise EvaluationConfigurationError("Diagnostic message cannot be blank when provided.")
        object.__setattr__(self, "code", code)
        if self.message is not None:
            object.__setattr__(self, "message", self.message.strip())


@dataclass(frozen=True, slots=True)
class GradeResult:
    passed: bool
    failure_reason: FailureReason | None = None
    diagnostic: SafeDiagnostic | None = None

    def __post_init__(self) -> None:
        if self.passed and (self.failure_reason is not None or self.diagnostic is not None):
            raise EvaluationConfigurationError(
                "A passing grade cannot contain failure information."
            )


@dataclass(frozen=True, slots=True)
class TestEvaluationResult:
    test_case_id: str
    grade: GradeResult

    def __post_init__(self) -> None:
        test_case_id = self.test_case_id.strip()
        if not test_case_id:
            raise EvaluationConfigurationError("Evaluated test-case ID cannot be blank.")
        object.__setattr__(self, "test_case_id", test_case_id)


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    test_results: tuple[TestEvaluationResult, ...]

    def __post_init__(self) -> None:
        test_results = tuple(self.test_results)
        if not test_results:
            raise EvaluationConfigurationError("An evaluation result requires at least one test.")
        test_ids = tuple(result.test_case_id for result in test_results)
        if len(set(test_ids)) != len(test_ids):
            raise EvaluationConfigurationError("Evaluated test-case IDs must be unique.")
        object.__setattr__(self, "test_results", test_results)

    @property
    def passed_count(self) -> int:
        return sum(result.grade.passed for result in self.test_results)

    @property
    def total_count(self) -> int:
        return len(self.test_results)

    @property
    def accuracy(self) -> float:
        return self.passed_count / self.total_count * 100.0
