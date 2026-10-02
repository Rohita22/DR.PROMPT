from datetime import datetime

from pydantic import BaseModel

from app.application.profile import CurrentUserProfileResult
from app.domains.auth import ApplicationUser
from app.domains.progression import UserProgressSummary


class MeResponse(BaseModel):
    id: str
    email: str | None
    username: str | None

    @classmethod
    def from_user(cls, user: ApplicationUser) -> "MeResponse":
        return cls(id=user.id, email=user.email, username=user.username)


class ChallengeProgressResponse(BaseModel):
    challenge: str
    best_score: float
    best_stars: int
    attempts: int
    completed: bool
    completed_at: datetime | None


class MeProgressResponse(BaseModel):
    total_xp: int
    challenges_completed: int
    stars_earned: int
    challenges: list[ChallengeProgressResponse]

    @classmethod
    def from_application_result(cls, result: UserProgressSummary) -> "MeProgressResponse":
        return cls(
            total_xp=result.total_xp,
            challenges_completed=result.challenges_completed,
            stars_earned=result.stars_earned,
            challenges=[
                ChallengeProgressResponse(
                    challenge=item.challenge_slug,
                    best_score=round(item.best_score, 2),
                    best_stars=item.best_stars,
                    attempts=item.attempts,
                    completed=item.completed,
                    completed_at=item.completed_at,
                )
                for item in result.challenges
            ],
        )


class ProfileLevelProgressResponse(BaseModel):
    level_floor: int
    next_level_at: int
    earned_in_level: int
    required_in_level: int


class ProfileChallengeStatsResponse(BaseModel):
    completed: int
    total: int


class ProfileStarStatsResponse(BaseModel):
    earned: int
    total: int


class ProfileActivityResponse(BaseModel):
    challenge: str
    title: str
    score: float
    accuracy: float
    stars: int
    prompt_tokens: int
    xp_earned: int
    submitted_at: datetime


class MeProfileResponse(BaseModel):
    player: str
    level: int
    level_progress: ProfileLevelProgressResponse
    total_xp: int
    challenges: ProfileChallengeStatsResponse
    stars: ProfileStarStatsResponse
    three_star_completions: int
    best_leaderboard_position: int | None
    recent_activity: list[ProfileActivityResponse]

    @classmethod
    def from_application_result(
        cls,
        result: CurrentUserProfileResult,
    ) -> "MeProfileResponse":
        return cls(
            player=result.player,
            level=result.level,
            level_progress=ProfileLevelProgressResponse(
                level_floor=result.level_progress.level_floor,
                next_level_at=result.level_progress.next_level_at,
                earned_in_level=result.level_progress.earned_in_level,
                required_in_level=result.level_progress.required_in_level,
            ),
            total_xp=result.total_xp,
            challenges=ProfileChallengeStatsResponse(
                completed=result.challenges_completed,
                total=result.total_challenges,
            ),
            stars=ProfileStarStatsResponse(
                earned=result.stars_earned,
                total=result.total_stars,
            ),
            three_star_completions=result.three_star_completions,
            best_leaderboard_position=result.best_leaderboard_position,
            recent_activity=[
                ProfileActivityResponse(
                    challenge=item.challenge_slug,
                    title=item.challenge_title,
                    score=round(item.score, 2),
                    accuracy=round(item.accuracy, 2),
                    stars=item.stars,
                    prompt_tokens=item.prompt_tokens,
                    xp_earned=item.xp_earned,
                    submitted_at=item.submitted_at,
                )
                for item in result.recent_activity
            ],
        )
