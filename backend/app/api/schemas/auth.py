from datetime import datetime

from pydantic import BaseModel

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
