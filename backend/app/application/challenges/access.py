from app.application.challenges.errors import (
    ChallengeAuthenticationRequiredError,
    ChallengeLockedError,
)
from app.domains.challenges.models import ChallengeTrack, PlayableChallenge
from app.domains.challenges.ports import ChallengeReader
from app.domains.progression import (
    ChallengeAccess,
    ChallengeProgressionService,
    UserProgressReader,
)


class ChallengeAccessService:
    def __init__(
        self,
        challenge_reader: ChallengeReader,
        progress_reader: UserProgressReader,
        progression_service: ChallengeProgressionService | None = None,
    ) -> None:
        self._challenge_reader = challenge_reader
        self._progress_reader = progress_reader
        self._progression = progression_service or ChallengeProgressionService()

    async def list_track(
        self,
        track: ChallengeTrack,
        user_id: str | None,
    ) -> tuple[ChallengeAccess, ...]:
        challenges = await self._challenge_reader.list_published(track)
        progress = ()
        if user_id is not None:
            progress = (await self._progress_reader.get_summary(user_id)).challenges
        return self._progression.evaluate_path(challenges, progress)

    async def resolve(
        self,
        playable: PlayableChallenge,
        user_id: str | None,
    ) -> ChallengeAccess:
        path = await self.list_track(playable.challenge.track, user_id)
        return next(item for item in path if item.challenge.challenge.id == playable.challenge.id)

    async def require_access(
        self,
        playable: PlayableChallenge,
        user_id: str | None,
    ) -> ChallengeAccess:
        access = await self.resolve(playable, user_id)
        if access.accessible:
            return access
        if user_id is None:
            raise ChallengeAuthenticationRequiredError()
        raise ChallengeLockedError()
