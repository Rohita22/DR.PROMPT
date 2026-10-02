from app.application.leaderboard.errors import LeaderboardRequestError
from app.application.leaderboard.models import (
    ChallengeLeaderboardResult,
    LeaderboardEntryResult,
)
from app.domains.challenges.errors import ChallengeNotFoundError
from app.domains.challenges.ports import ChallengeReader
from app.domains.leaderboard import LeaderboardReader, RankedLeaderboardSubmission


class GetChallengeLeaderboardUseCase:
    def __init__(
        self,
        challenge_reader: ChallengeReader,
        leaderboard_reader: LeaderboardReader,
    ) -> None:
        self._challenge_reader = challenge_reader
        self._leaderboard_reader = leaderboard_reader

    async def execute(
        self,
        challenge_slug: str,
        *,
        limit: int = 25,
        offset: int = 0,
        current_user_id: str | None = None,
    ) -> ChallengeLeaderboardResult:
        if not 1 <= limit <= 100:
            raise LeaderboardRequestError("Leaderboard limit must be between 1 and 100.")
        if offset < 0:
            raise LeaderboardRequestError("Leaderboard offset cannot be negative.")

        playable = await self._challenge_reader.get_by_slug(challenge_slug)
        if playable is None:
            raise ChallengeNotFoundError(f"Published challenge '{challenge_slug}' was not found.")
        version = playable.version
        page = await self._leaderboard_reader.get_page(
            challenge_id=playable.challenge.id,
            challenge_version_id=version.version_id,
            model_identifier=version.model_config.model_id,
            model_configuration_version=version.model_config.configuration_version,
            limit=limit,
            offset=offset,
            current_user_id=current_user_id,
        )

        def to_result(entry: RankedLeaderboardSubmission) -> LeaderboardEntryResult:
            return LeaderboardEntryResult(
                rank=entry.rank,
                player=entry.player,
                score=entry.score,
                accuracy=entry.accuracy,
                prompt_tokens=entry.prompt_tokens,
                stars=entry.stars,
                submitted_at=entry.submitted_at,
                is_current_user=(current_user_id is not None and entry.user_id == current_user_id),
            )

        return ChallengeLeaderboardResult(
            challenge_slug=playable.challenge.slug,
            challenge_version_id=version.version_id,
            entries=tuple(to_result(entry) for entry in page.entries),
            current_user_entry=(
                to_result(page.current_user_entry) if page.current_user_entry is not None else None
            ),
            total_entries=page.total_entries,
            limit=limit,
            offset=offset,
        )
