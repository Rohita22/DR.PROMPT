from typing import Protocol

from app.domains.challenges.models import ChallengeTrack, PlayableChallenge


class ChallengeReader(Protocol):
    """Minimal read boundary for the current published challenge version."""

    async def get_by_slug(self, slug: str) -> PlayableChallenge | None: ...

    async def list_published(
        self,
        track: ChallengeTrack | None = None,
    ) -> tuple[PlayableChallenge, ...]: ...
