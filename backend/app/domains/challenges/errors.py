from app.core.exceptions import DomainError


class ChallengeDefinitionError(DomainError):
    """Raised when a challenge definition would enter an invalid state."""

    code = "invalid_challenge_definition"


class ChallengeNotFoundError(DomainError):
    """Raised when no published challenge exists for a requested identifier."""

    code = "challenge_not_found"
