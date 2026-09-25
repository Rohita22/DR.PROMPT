from app.core.exceptions import DomainError


class RunChallengeRequestError(DomainError):
    code = "invalid_run_challenge_request"
