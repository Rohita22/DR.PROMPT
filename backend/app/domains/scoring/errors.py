from app.core.exceptions import DomainError


class ScoringConfigurationError(DomainError):
    """Raised when scoring configuration is internally inconsistent."""

    code = "invalid_scoring_configuration"
