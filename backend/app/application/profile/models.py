from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class LevelProgressResult:
    level_floor: int
    next_level_at: int
    earned_in_level: int
    required_in_level: int


@dataclass(frozen=True, slots=True)
class ProfileActivityResult:
    challenge_slug: str
    challenge_title: str
    score: float
    accuracy: float
    stars: int
    prompt_tokens: int
    xp_earned: int
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class CurrentUserProfileResult:
    player: str
    level: int
    level_progress: LevelProgressResult
    total_xp: int
    challenges_completed: int
    total_challenges: int
    stars_earned: int
    total_stars: int
    three_star_completions: int
    best_leaderboard_position: int | None
    recent_activity: tuple[ProfileActivityResult, ...]
