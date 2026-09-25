from app.domains.challenges.errors import ChallengeDefinitionError
from app.domains.challenges.models import ChallengeTrack, PlayableChallenge
from app.infrastructure.challenges.control_fixtures import (
    CONTROL_BOSS_CHALLENGE,
    CONTROL_CHALLENGES,
    EXACT_OUTPUT_CHALLENGE,
    FORMATTING_RULES_CHALLENGE,
    MULTIPLE_CONSTRAINTS_CHALLENGE,
    OUTPUT_RESTRICTIONS_CHALLENGE,
)

__all__ = [
    "CONTROL_BOSS_CHALLENGE",
    "CONTROL_CHALLENGES",
    "EXACT_OUTPUT_CHALLENGE",
    "FORMATTING_RULES_CHALLENGE",
    "InMemoryChallengeRepository",
    "MULTIPLE_CONSTRAINTS_CHALLENGE",
    "OUTPUT_RESTRICTIONS_CHALLENGE",
]


class InMemoryChallengeRepository:
    """Immutable ordered fixtures implementing the public challenge reader."""

    def __init__(self, challenges: tuple[PlayableChallenge, ...] | None = None) -> None:
        items = CONTROL_CHALLENGES if challenges is None else tuple(challenges)
        by_slug = {item.challenge.slug: item for item in items}
        if len(by_slug) != len(items):
            raise ChallengeDefinitionError("In-memory challenge slugs must be unique.")
        self._by_slug = by_slug

    async def get_by_slug(self, slug: str) -> PlayableChallenge | None:
        return self._by_slug.get(slug)

    async def list_published(
        self,
        track: ChallengeTrack | None = None,
    ) -> tuple[PlayableChallenge, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._by_slug.values()
                    if track is None or item.challenge.track is track
                ),
                key=lambda item: (item.challenge.track.value, item.challenge.order),
            )
        )
