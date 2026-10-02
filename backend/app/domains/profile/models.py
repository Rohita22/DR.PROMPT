from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from app.core.exceptions import DomainError


@dataclass(frozen=True, slots=True)
class LevelConfiguration:
    xp_per_level: int = 500

    def __post_init__(self) -> None:
        if self.xp_per_level <= 0:
            raise DomainError("XP per level must be positive.")


DEFAULT_LEVEL_CONFIGURATION = LevelConfiguration()


@dataclass(frozen=True, slots=True)
class LevelProgress:
    level: int
    level_floor: int
    next_level_at: int
    earned_in_level: int
    required_in_level: int


def calculate_level(
    total_xp: int,
    configuration: LevelConfiguration = DEFAULT_LEVEL_CONFIGURATION,
) -> LevelProgress:
    if total_xp < 0:
        raise DomainError("Total XP cannot be negative.")
    level = total_xp // configuration.xp_per_level + 1
    level_floor = (level - 1) * configuration.xp_per_level
    next_level_at = level * configuration.xp_per_level
    return LevelProgress(
        level=level,
        level_floor=level_floor,
        next_level_at=next_level_at,
        earned_in_level=total_xp - level_floor,
        required_in_level=configuration.xp_per_level,
    )


@dataclass(frozen=True, slots=True)
class ProfileActivity:
    challenge_slug: str
    challenge_title: str
    score: float
    accuracy: float
    stars: int
    prompt_tokens: int
    xp_earned: int
    submitted_at: datetime

    def __post_init__(self) -> None:
        if not self.challenge_slug.strip() or not self.challenge_title.strip():
            raise DomainError("Profile activity challenge identity cannot be blank.")
        if any(
            not isfinite(value) or not 0 <= value <= 100 for value in (self.score, self.accuracy)
        ):
            raise DomainError("Profile activity scores must be between 0 and 100.")
        if not 0 <= self.stars <= 3:
            raise DomainError("Profile activity stars must be between 0 and 3.")
        if self.prompt_tokens < 0 or self.xp_earned < 0:
            raise DomainError("Profile activity counts cannot be negative.")
        if self.submitted_at.tzinfo is None or self.submitted_at.utcoffset() is None:
            raise DomainError("Profile activity timestamp must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class ProfileSnapshot:
    total_xp: int
    published_challenges: int
    challenges_completed: int
    stars_earned: int
    three_star_completions: int
    best_leaderboard_rank: int | None
    recent_activity: tuple[ProfileActivity, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "recent_activity", tuple(self.recent_activity))
        counts = (
            self.total_xp,
            self.published_challenges,
            self.challenges_completed,
            self.stars_earned,
            self.three_star_completions,
        )
        if any(value < 0 for value in counts):
            raise DomainError("Profile counts cannot be negative.")
        if self.challenges_completed > self.published_challenges:
            raise DomainError("Completed challenges cannot exceed published challenges.")
        if self.stars_earned > self.published_challenges * 3:
            raise DomainError("Earned stars cannot exceed available stars.")
        if self.three_star_completions > self.challenges_completed:
            raise DomainError("Perfect clears cannot exceed completed challenges.")
        if self.best_leaderboard_rank is not None and self.best_leaderboard_rank <= 0:
            raise DomainError("Leaderboard rank must be positive.")
