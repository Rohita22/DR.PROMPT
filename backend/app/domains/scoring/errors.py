from app.core.exceptions import DomainError


class ScoringConfigurationError(DomainError):
    """Raised when scoring configuration is internally inconsistent."""

    code = "invalid_scoring_configuration"


class ScoringInputError(DomainError):
    """Raised when runtime scoring inputs fall outside their valid ranges."""

    code = "invalid_scoring_input"


class TokenizationError(DomainError):
    """Raised when authoritative local prompt tokenization is unavailable."""

    code = "tokenization_error"
