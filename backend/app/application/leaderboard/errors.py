from app.core.exceptions import DomainError


class LeaderboardRequestError(DomainError):
    code = "invalid_leaderboard_request"
