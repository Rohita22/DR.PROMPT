from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite

from app.core.exceptions import DomainError


class XPAwardReason(StrEnum):
    FIRST_COMPLETION = "first_completion"
    TWO_STAR = "two_star"
    THREE_STAR = "three_star"
    BOSS_COMPLETION = "boss_completion"


@dataclass(frozen=True, slots=True)
class XPRewardConfiguration:
    first_completion: int = 100
    two_star: int = 25
    three_star: int = 50
    boss_completion: int = 250
    boss_replaces_first_completion: bool = True

    def __post_init__(self) -> None:
        if any(
            reward < 0
            for reward in (
                self.first_completion,
                self.two_star,
                self.three_star,
                self.boss_completion,
            )
        ):
            raise DomainError("XP rewards cannot be negative.")


@dataclass(frozen=True, slots=True)
class UserChallengeProgress:
    id: str
    user_id: str
    challenge_id: str
    best_submission_id: str
    best_score: float
    best_stars: int
    attempts: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        identifiers = (self.id, self.user_id, self.challenge_id, self.best_submission_id)
        if any(not value.strip() for value in identifiers):
            raise DomainError("Progress identifiers cannot be blank.")
        if not isfinite(self.best_score) or not 0 <= self.best_score <= 100:
            raise DomainError("Best score must be between 0 and 100.")
        if not 0 <= self.best_stars <= 3:
            raise DomainError("Best stars must be between 0 and 3.")
        if self.attempts <= 0:
            raise DomainError("Progress attempts must be positive.")
        timestamps = (self.created_at, self.updated_at)
        if self.completed_at is not None:
            timestamps += (self.completed_at,)
        if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps):
            raise DomainError("Progress timestamps must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class XPAward:
    reason: XPAwardReason
    amount: int

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise DomainError("XP awards must be positive.")


@dataclass(frozen=True, slots=True)
class XPTransaction:
    id: str
    user_id: str
    challenge_id: str
    submission_id: str
    reason: XPAwardReason
    amount: int
    created_at: datetime

    def __post_init__(self) -> None:
        identifiers = (self.id, self.user_id, self.challenge_id, self.submission_id)
        if any(not value.strip() for value in identifiers):
            raise DomainError("XP transaction identifiers cannot be blank.")
        if self.amount <= 0:
            raise DomainError("XP transaction amount must be positive.")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise DomainError("XP transaction timestamp must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class ProgressionResult:
    progress: UserChallengeProgress
    awards: tuple[XPAward, ...]
    total_xp: int

    @property
    def xp_earned(self) -> int:
        return sum(award.amount for award in self.awards)


@dataclass(frozen=True, slots=True)
class UserProgressItem:
    challenge_slug: str
    best_score: float
    best_stars: int
    attempts: int
    completed_at: datetime | None

    @property
    def completed(self) -> bool:
        return self.completed_at is not None


@dataclass(frozen=True, slots=True)
class UserProgressSummary:
    total_xp: int
    challenges_completed: int
    stars_earned: int
    challenges: tuple[UserProgressItem, ...]
