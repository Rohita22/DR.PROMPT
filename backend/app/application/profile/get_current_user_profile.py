from app.application.profile.models import (
    CurrentUserProfileResult,
    LevelProgressResult,
    ProfileActivityResult,
)
from app.domains.auth import ApplicationUser
from app.domains.leaderboard import leaderboard_display_name
from app.domains.profile import (
    DEFAULT_LEVEL_CONFIGURATION,
    LevelConfiguration,
    ProfileReader,
    calculate_level,
)


class GetCurrentUserProfileUseCase:
    def __init__(
        self,
        reader: ProfileReader,
        level_configuration: LevelConfiguration = DEFAULT_LEVEL_CONFIGURATION,
        *,
        recent_limit: int = 5,
    ) -> None:
        if recent_limit <= 0:
            raise ValueError("Recent activity limit must be positive.")
        self._reader = reader
        self._level_configuration = level_configuration
        self._recent_limit = recent_limit

    async def execute(self, user: ApplicationUser) -> CurrentUserProfileResult:
        snapshot = await self._reader.get_snapshot(
            user.id,
            recent_limit=self._recent_limit,
        )
        level = calculate_level(snapshot.total_xp, self._level_configuration)
        return CurrentUserProfileResult(
            player=leaderboard_display_name(user.username, user.id),
            level=level.level,
            level_progress=LevelProgressResult(
                level_floor=level.level_floor,
                next_level_at=level.next_level_at,
                earned_in_level=level.earned_in_level,
                required_in_level=level.required_in_level,
            ),
            total_xp=snapshot.total_xp,
            challenges_completed=snapshot.challenges_completed,
            total_challenges=snapshot.published_challenges,
            stars_earned=snapshot.stars_earned,
            total_stars=snapshot.published_challenges * 3,
            three_star_completions=snapshot.three_star_completions,
            best_leaderboard_position=snapshot.best_leaderboard_rank,
            recent_activity=tuple(
                ProfileActivityResult(
                    challenge_slug=item.challenge_slug,
                    challenge_title=item.challenge_title,
                    score=item.score,
                    accuracy=item.accuracy,
                    stars=item.stars,
                    prompt_tokens=item.prompt_tokens,
                    xp_earned=item.xp_earned,
                    submitted_at=item.submitted_at,
                )
                for item in snapshot.recent_activity
            ),
        )
