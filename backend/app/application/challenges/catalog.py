from app.application.challenges.access import ChallengeAccessService
from app.domains.application.ports import StarterPreviewReader
from app.domains.challenges.errors import ChallengeNotFoundError
from app.domains.challenges.models import ChallengeTrack, PlayableChallenge
from app.domains.challenges.ports import ChallengeReader
from app.domains.progression import ChallengeAccess


class ListChallengesUseCase:
    def __init__(self, access_service: ChallengeAccessService) -> None:
        self._access_service = access_service

    async def execute(
        self,
        user_id: str | None,
        track: ChallengeTrack = ChallengeTrack.CONTROL,
    ) -> tuple[ChallengeAccess, ...]:
        return await self._access_service.list_track(track, user_id)


class GetChallengeDetailUseCase:
    def __init__(
        self,
        challenge_reader: ChallengeReader,
        access_service: ChallengeAccessService,
    ) -> None:
        self._challenge_reader = challenge_reader
        self._access_service = access_service

    async def execute(
        self,
        challenge_slug: str,
        user_id: str | None,
    ) -> tuple[PlayableChallenge, ChallengeAccess]:
        playable = await self._challenge_reader.get_by_slug(challenge_slug)
        if playable is None:
            raise ChallengeNotFoundError(f"Published challenge '{challenge_slug}' was not found.")
        access = await self._access_service.require_access(playable, user_id)
        return playable, access


class GetStarterPreviewUseCase:
    """Return the committed starter screenshot for a published APPLICATION challenge.

    The unmodified starter is public reference material (it contains no hidden checks),
    so this read is not progression-gated.
    """

    def __init__(self, challenge_reader: ChallengeReader, previews: StarterPreviewReader) -> None:
        self._challenge_reader = challenge_reader
        self._previews = previews

    async def execute(self, challenge_slug: str, viewport: str) -> bytes:
        playable = await self._challenge_reader.get_by_slug(challenge_slug)
        config = playable.version.application_config if playable is not None else None
        preview = (
            self._previews.preview_png(config.starter_project, viewport)
            if config is not None
            else None
        )
        if preview is None:
            raise ChallengeNotFoundError("Starter preview was not found.")
        return preview
