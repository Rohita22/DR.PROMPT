from typing import Protocol

from app.domains.challenges.models import PlayableChallenge


class ChallengeReader(Protocol):
    """Minimal read boundary for the current published challenge version."""

    def get_by_slug(self, slug: str) -> PlayableChallenge | None: ...
