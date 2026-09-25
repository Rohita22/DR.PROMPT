from app.core.exceptions import DomainError


class EvaluationConfigurationError(DomainError):
    """Raised when evaluation configuration or results are internally inconsistent."""

    code = "invalid_evaluation_configuration"


class UnsupportedGraderError(EvaluationConfigurationError):
    """Raised when no grader is registered for a typed configuration."""

    code = "unsupported_grader"


class EvaluationBatchError(EvaluationConfigurationError):
    """Raised when test cases and supplied outputs cannot be associated safely."""

    code = "invalid_evaluation_batch"
