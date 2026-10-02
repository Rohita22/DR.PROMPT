from app.core.exceptions import DomainError


class AdminChallengeNotFoundError(DomainError):
    code = "admin_challenge_not_found"


class AdminChallengeConflictError(DomainError):
    code = "admin_challenge_conflict"


class AdminChallengeStateError(DomainError):
    code = "admin_challenge_state_error"
