from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from math import isfinite

from app.core.exceptions import DomainError


def leaderboard_display_name(username: str | None, user_id: str) -> str:
    """Return a public label without exposing email, provider identity, or raw UUID."""

    if username is not None and username.strip():
        return username.strip()
    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise DomainError("Leaderboard user ID cannot be blank.")
    suffix = sha256(normalized_user_id.encode("utf-8")).hexdigest()[:4].upper()
    return f"Player-{suffix}"


@dataclass(frozen=True, slots=True)
class LeaderboardSubmissionCandidate:
    submission_id: str
    user_id: str
    username: str | None
    score: float
    accuracy: float
    prompt_tokens: int
    stars: int
    submitted_at: datetime

    def __post_init__(self) -> None:
        if not self.submission_id.strip() or not self.user_id.strip():
            raise DomainError("Leaderboard identifiers cannot be blank.")
        if self.username is not None:
            normalized_username = self.username.strip()
            object.__setattr__(self, "username", normalized_username or None)
        if any(
            not isfinite(value) or not 0 <= value <= 100 for value in (self.score, self.accuracy)
        ):
            raise DomainError("Leaderboard scores must be between 0 and 100.")
        if self.prompt_tokens < 0:
            raise DomainError("Leaderboard prompt tokens cannot be negative.")
        if not 0 <= self.stars <= 3:
            raise DomainError("Leaderboard stars must be between 0 and 3.")
        if self.submitted_at.tzinfo is None or self.submitted_at.utcoffset() is None:
            raise DomainError("Leaderboard timestamps must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class RankedLeaderboardSubmission(LeaderboardSubmissionCandidate):
    rank: int

    def __post_init__(self) -> None:
        LeaderboardSubmissionCandidate.__post_init__(self)
        if self.rank <= 0:
            raise DomainError("Leaderboard rank must be positive.")

    @property
    def player(self) -> str:
        return leaderboard_display_name(self.username, self.user_id)


def rank_best_submissions(
    candidates: tuple[LeaderboardSubmissionCandidate, ...],
) -> tuple[RankedLeaderboardSubmission, ...]:
    """Canonical in-memory form of the PostgreSQL leaderboard ordering."""

    def ranking_key(candidate: LeaderboardSubmissionCandidate) -> tuple[object, ...]:
        return (
            -candidate.score,
            -candidate.accuracy,
            candidate.prompt_tokens,
            candidate.submitted_at,
            candidate.submission_id,
        )

    best_by_user: dict[str, LeaderboardSubmissionCandidate] = {}
    for candidate in candidates:
        existing = best_by_user.get(candidate.user_id)
        if existing is None or ranking_key(candidate) < ranking_key(existing):
            best_by_user[candidate.user_id] = candidate
    ordered = sorted(best_by_user.values(), key=ranking_key)
    return tuple(
        RankedLeaderboardSubmission(
            rank=index,
            submission_id=item.submission_id,
            user_id=item.user_id,
            username=item.username,
            score=item.score,
            accuracy=item.accuracy,
            prompt_tokens=item.prompt_tokens,
            stars=item.stars,
            submitted_at=item.submitted_at,
        )
        for index, item in enumerate(ordered, start=1)
    )


@dataclass(frozen=True, slots=True)
class LeaderboardPage:
    entries: tuple[RankedLeaderboardSubmission, ...]
    total_entries: int
    current_user_entry: RankedLeaderboardSubmission | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        if self.total_entries < 0 or self.total_entries < len(self.entries):
            raise DomainError("Leaderboard total is invalid.")
