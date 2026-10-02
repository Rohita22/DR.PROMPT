from app.core.exceptions import DomainError


class ChallengeExecutionError(DomainError):
    """Raised when an execution request or normalized result is internally inconsistent."""

    code = "invalid_challenge_execution"


class UnsupportedChallengeTypeError(DomainError):
    """Raised when no executor is registered for a challenge's type; never falls back."""

    code = "unsupported_challenge_type"

    def __init__(self, challenge_type: str) -> None:
        super().__init__(f"Challenge type '{challenge_type}' cannot be executed.")
        self.challenge_type = challenge_type
