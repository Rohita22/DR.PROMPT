from app.core.exceptions import AuthenticationError, AuthorizationError, DomainError


class RunChallengeRequestError(DomainError):
    code = "invalid_run_challenge_request"


class SubmitChallengeRequestError(DomainError):
    """Raised when a Submit command is invalid before evaluation begins."""

    code = "invalid_submit_challenge_request"


class PromptTooLongError(DomainError):
    """Raised before execution when a player prompt exceeds the challenge hard limit."""

    code = "prompt_too_long"

    def __init__(self, *, actual_tokens: int, maximum_tokens: int) -> None:
        super().__init__(
            f"Prompt contains {actual_tokens} tokens; maximum allowed is {maximum_tokens}."
        )
        self.actual_tokens = actual_tokens
        self.maximum_tokens = maximum_tokens


class ChallengeLockedError(AuthorizationError):
    code = "challenge_locked"

    def __init__(self) -> None:
        super().__init__("Complete the previous challenge to unlock this challenge.")


class ChallengeAuthenticationRequiredError(AuthenticationError):
    code = "challenge_authentication_required"

    def __init__(self) -> None:
        super().__init__("Sign in and complete the previous challenge to continue.")
